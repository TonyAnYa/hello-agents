"""测试在线政策 LLM 概念发现与本地证据校验。"""

import json
from datetime import date

from enterprise_concept_radar.agents.concept_discovery_agent import (
    discover_policy_concepts,
)
from enterprise_concept_radar.models import (
    BaselineTerm,
    ConceptBaseline,
    ConceptCandidateType,
    PolicyDocument,
    PolicyDocumentType,
)


def build_document() -> PolicyDocument:
    """创建真实政策文档。"""
    return PolicyDocument(
        document_id="online-policy-1",
        title="关于推进多主体绿电直连的通知",
        source_name="国家能源局",
        source_url=(
            "https://example.com/policy"
        ),
        published_date=date(2026, 8, 7),
        document_type=(
            PolicyDocumentType.NOTICE
        ),
        content=(
            "关于推进多主体绿电直连的通知。\n"
            "探索多主体绿电直连协同结算机制，"
            "完善项目接入和市场交易规则。\n"
            "本通知自发布之日起实施。"
        ),
        is_simulated=False,
    )


def build_baseline() -> ConceptBaseline:
    """创建历史术语基线。"""
    return ConceptBaseline(
        baseline_name="test",
        version="1",
        known_terms=[
            BaselineTerm(
                term="绿电直连",
                aliases=[],
            )
        ],
    )


class DiscoveryAgent:
    """返回一条真实证据和一条伪造证据。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        assert "多主体绿电直连" in input_text
        assert kwargs["max_tokens"] == 1800

        return json.dumps(
            {
                "candidates": [
                    {
                        "term": "多主体绿电直连",
                        "evidence_quote": (
                            "探索多主体绿电直连协同结算机制，"
                            "完善项目接入和市场交易规则。"
                        ),
                        "confidence": 0.94,
                        "reason": "在已有概念上增加多主体限定。",
                    },
                    {
                        "term": "虚构机制",
                        "evidence_quote": "政策提出虚构机制。",
                        "confidence": 0.99,
                        "reason": "该证据并不存在。",
                    },
                ]
            },
            ensure_ascii=False,
        )


def test_discovery_keeps_only_verified_evidence() -> None:
    """伪造证据必须被本地程序过滤。"""
    candidates = discover_policy_concepts(
        document=build_document(),
        baseline=build_baseline(),
        question="有哪些新概念？",
        focus_keywords=["绿电直连"],
        agent=DiscoveryAgent(),
    )

    assert len(candidates) == 1
    assert candidates[0].term == (
        "多主体绿电直连"
    )
    assert candidates[0].candidate_type == (
        ConceptCandidateType.NEW_EXPRESSION
    )
    assert candidates[0].novelty_score == 82


class LowConfidenceAgent:
    """返回低置信度候选。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        return json.dumps(
            {
                "candidates": [
                    {
                        "term": "多主体绿电直连",
                        "evidence_quote": (
                            "探索多主体绿电直连协同结算机制，"
                            "完善项目接入和市场交易规则。"
                        ),
                        "confidence": 0.4,
                        "reason": "置信度不足。",
                    }
                ]
            },
            ensure_ascii=False,
        )


def test_discovery_filters_low_confidence() -> None:
    """低于用户阈值的候选不进入深入分析。"""
    candidates = discover_policy_concepts(
        document=build_document(),
        baseline=build_baseline(),
        question="有哪些新概念？",
        focus_keywords=["绿电直连"],
        minimum_confidence=0.65,
        agent=LowConfidenceAgent(),
    )

    assert candidates == []
