"""测试按政策来源执行真实搜索。"""

from enterprise_concept_radar.policy_sources import (
    PolicySourceKind,
    PolicySourceSlot,
)
from enterprise_concept_radar.services.policy_search import (
    build_policy_search_query,
    search_policy_candidates,
)


class FakeResponse:
    """SerpAPI 测试响应。"""

    def raise_for_status(self) -> None:
        """模拟成功响应。"""

    def json(self):
        return {
            "organic_results": [
                {
                    "position": 1,
                    "title": "关于测试政策的通知",
                    "link": (
                        "https://www.nea.gov.cn/test.html"
                    ),
                    "snippet": "国家能源局发布测试政策。",
                },
                {
                    "position": 2,
                    "title": "关于测试政策的通知",
                    "link": (
                        "https://www.nea.gov.cn/test.html"
                    ),
                    "snippet": "重复结果。",
                },
            ]
        }


class FakeSession:
    """记录 SerpAPI 查询参数。"""

    def get(self, url: str, **kwargs):
        assert url.endswith("/search.json")
        assert kwargs["params"]["api_key"] == "test-key"
        assert kwargs["params"]["engine"] == "google"
        return FakeResponse()


def build_nea_source() -> PolicySourceSlot:
    """创建启用的国家能源局来源。"""
    return PolicySourceSlot(
        slot=1,
        source_id="nea",
        kind=PolicySourceKind.BUILTIN,
        name="国家能源局",
        entry_url="https://www.nea.gov.cn/",
        enabled=True,
    )


def test_build_policy_search_query_limits_domain() -> None:
    """指定来源时应使用 site 域名限制。"""
    query = build_policy_search_query(
        source=build_nea_source(),
        question="近期有哪些新能源政策？",
        keywords=[
            "新能源",
            "电力市场",
        ],
    )

    assert "site:www.nea.gov.cn" in query
    assert "新能源" in query
    assert "电力市场" in query


def test_search_policy_candidates_deduplicates_urls() -> None:
    """相同 URL 只应保留一次。"""
    results = search_policy_candidates(
        source=build_nea_source(),
        question="近期有哪些新能源政策？",
        keywords=["新能源"],
        api_key="test-key",
        session=FakeSession(),
    )

    assert len(results) == 1
    assert results[0].source_slot == 1
    assert results[0].url == (
        "https://www.nea.gov.cn/test.html"
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
