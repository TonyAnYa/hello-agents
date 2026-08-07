"""测试 LLM 政策源解析。"""

import json

import pytest

from enterprise_concept_radar.agents import (
    PolicySourceResolverError,
    resolve_policy_source,
)
from enterprise_concept_radar.policy_sources import (
    PolicySourceSearchCandidate,
)


def build_candidates():
    """创建官网搜索候选。"""
    return [
        PolicySourceSearchCandidate(
            position=1,
            title="普通新闻页面",
            url="https://example.com/news",
            snippet="新闻转载。",
        ),
        PolicySourceSearchCandidate(
            position=2,
            title="国务院国有资产监督管理委员会",
            url="https://www.sasac.gov.cn/",
            snippet="国务院国资委官方网站。",
        ),
    ]


def test_llm_can_select_official_source() -> None:
    """LLM 应从候选结果中选择官网。"""

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            assert "国资委" in input_text
            assert kwargs["max_tokens"] == 900

            return json.dumps(
                {
                    "official_name": (
                        "国务院国有资产监督管理委员会"
                    ),
                    "selected_candidate_index": 1,
                    "confidence": 0.98,
                    "reason": "候选页面为机构官方网站。",
                },
                ensure_ascii=False,
            )

    resolution = resolve_policy_source(
        requested_name="国资委",
        candidates=build_candidates(),
        agent=FakeAgent(),
    )

    assert resolution.entry_url == (
        "https://www.sasac.gov.cn/"
    )
    assert resolution.source_domain == "www.sasac.gov.cn"
    assert resolution.confidence == 0.98


def test_llm_cannot_invent_candidate_index() -> None:
    """LLM 不能选择候选列表之外的网址。"""

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            return json.dumps(
                {
                    "official_name": "错误机构",
                    "selected_candidate_index": 99,
                    "confidence": 0.9,
                    "reason": "错误测试。",
                },
                ensure_ascii=False,
            )

    with pytest.raises(
        PolicySourceResolverError,
        match="超出范围",
    ):
        resolve_policy_source(
            requested_name="测试机构",
            candidates=build_candidates(),
            agent=FakeAgent(),
        )