"""测试按政策来源执行真实搜索。"""

from datetime import date

import pytest

from enterprise_concept_radar.policy_sources import (
    PolicySourceKind,
    PolicySourceSlot,
)
from enterprise_concept_radar.services.policy_search import (
    PolicySearchNoResultsError,
    build_policy_search_queries,
    build_policy_search_query,
    build_serpapi_date_filter,
    search_policy_candidates,
)
from enterprise_concept_radar.services.source_search import (
    PolicySourceSearchError,
)


class FakeResponse:
    """SerpAPI 测试响应。"""

    def __init__(
        self,
        payload,
    ) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        """模拟成功 HTTP 响应。"""

    def json(self):
        """返回测试 JSON。"""
        return self.payload


class FakeSession:
    """记录多次 SerpAPI 查询参数。"""

    def __init__(
        self,
        payloads,
    ) -> None:
        self.payloads = iter(
            payloads
        )
        self.calls = []

    def get(
        self,
        url: str,
        **kwargs,
    ):
        assert url.endswith(
            "/search.json"
        )
        assert (
            kwargs["params"]["api_key"]
            == "test-key"
        )
        assert (
            kwargs["params"]["engine"]
            == "google"
        )
        self.calls.append(
            kwargs["params"]
        )

        return FakeResponse(
            next(self.payloads)
        )


def build_nea_source() -> PolicySourceSlot:
    """创建启用的国家能源局来源。"""
    return PolicySourceSlot(
        slot=1,
        source_id="nea",
        kind=PolicySourceKind.BUILTIN,
        name="国家能源局",
        entry_url=(
            "https://www.nea.gov.cn/"
        ),
        enabled=True,
    )


def result_payload(
    *,
    url: str = (
        "https://www.nea.gov.cn/test.html"
    ),
):
    """创建包含一个候选的成功响应。"""
    return {
        "search_metadata": {
            "status": "Success",
        },
        "organic_results": [
            {
                "position": 1,
                "title": "关于测试政策的通知",
                "link": url,
                "snippet": (
                    "国家能源局发布测试政策。"
                ),
            }
        ],
    }


def empty_payload():
    """创建 SerpAPI 的成功但零结果响应。"""
    return {
        "search_metadata": {
            "status": "Success",
        },
        "search_information": {
            "organic_results_state": (
                "Fully empty"
            ),
        },
        "error": (
            "Google hasn't returned any "
            "results for this query."
        ),
    }


def test_query_uses_or_and_omits_full_question() -> None:
    """主题词应使用 OR，整段问题不应直接限制搜索。"""
    query = build_policy_search_query(
        source=build_nea_source(),
        question=(
            "今天有哪些能源政策出现了"
            "新的词语和制度安排？"
        ),
        keywords=[
            "新能源",
            "电力市场",
        ],
    )

    assert (
        "site:www.nea.gov.cn"
        in query
    )
    assert (
        '"新能源" OR "电力市场"'
        in query
    )
    assert "今天有哪些" not in query


def test_query_plan_has_broad_fallback() -> None:
    """第一条零结果时应有更宽的第二条查询。"""
    queries = (
        build_policy_search_queries(
            source=build_nea_source(),
            question="测试问题",
            keywords=[
                "新能源",
                "电力市场",
            ],
        )
    )

    assert len(queries) == 2
    assert "政策" in queries[0]
    assert "政策" not in queries[1]
    assert all(
        "site:www.nea.gov.cn"
        in query
        for query in queries
    )


def test_custom_date_filter_is_inclusive() -> None:
    """日期范围应通过 tbs 参数传递。"""
    value = (
        build_serpapi_date_filter(
            published_after=date(
                2026,
                8,
                5,
            ),
            published_before=date(
                2026,
                8,
                7,
            ),
        )
    )

    assert value == (
        "cdr:1,"
        "cd_min:08/05/2026,"
        "cd_max:08/07/2026"
    )


def test_search_uses_tbs_and_returns_result() -> None:
    """成功结果应保留并使用日期过滤参数。"""
    session = FakeSession(
        [result_payload()]
    )
    results = (
        search_policy_candidates(
            source=build_nea_source(),
            question="近期政策",
            keywords=["新能源"],
            published_after=date(
                2026,
                8,
                5,
            ),
            published_before=date(
                2026,
                8,
                7,
            ),
            api_key="test-key",
            session=session,
        )
    )

    assert len(results) == 1
    assert "tbs" in session.calls[0]
    assert (
        results[0].source_slot
        == 1
    )


def test_empty_primary_retries_broad_query() -> None:
    """第一条空结果时应自动执行第二条宽查询。"""
    session = FakeSession(
        [
            empty_payload(),
            result_payload(),
        ]
    )
    results = (
        search_policy_candidates(
            source=build_nea_source(),
            question="近期政策",
            keywords=["新能源"],
            api_key="test-key",
            session=session,
        )
    )

    assert len(results) == 1
    assert len(session.calls) == 2
    assert (
        session.calls[0]["q"]
        != session.calls[1]["q"]
    )


def test_all_empty_results_are_not_silent_success() -> None:
    """全部零结果必须成为可审计异常。"""
    session = FakeSession(
        [
            empty_payload(),
            empty_payload(),
        ]
    )

    with pytest.raises(
        PolicySearchNoResultsError,
        match="已尝试 2 条查询",
    ):
        search_policy_candidates(
            source=build_nea_source(),
            question="近期政策",
            keywords=["新能源"],
            api_key="test-key",
            session=session,
        )


def test_serpapi_error_status_is_raised() -> None:
    """SerpAPI Error 状态不能被当成空列表。"""
    session = FakeSession(
        [
            {
                "search_metadata": {
                    "status": "Error",
                },
                "error": (
                    "Invalid API key."
                ),
            }
        ]
    )

    with pytest.raises(
        PolicySourceSearchError,
        match="Invalid API key",
    ):
        search_policy_candidates(
            source=build_nea_source(),
            question="近期政策",
            keywords=["新能源"],
            api_key="test-key",
            session=session,
        )


def test_open_web_query_has_no_site_restriction() -> None:
    """全网搜索不得添加固定域名。"""
    source = PolicySourceSlot(
        slot=6,
        source_id="open-web",
        kind=PolicySourceKind.OPEN_WEB,
        name="不指定来源（全网搜索）",
        entry_url=None,
        enabled=True,
    )

    query = build_policy_search_query(
        source=source,
        question="新能源政策",
        keywords=["储能"],
    )

    assert "site:" not in query
    assert "储能" in query
