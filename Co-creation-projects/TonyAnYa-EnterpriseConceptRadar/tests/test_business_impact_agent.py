"""测试 BusinessImpactAgent 的结构化处理。"""

import json

import pytest

from enterprise_concept_radar.agents import (
    BusinessImpactError,
    assess_business_impact,
    parse_business_impact_response,
)
from enterprise_concept_radar.config import SAMPLE_POLICY_DIR
from enterprise_concept_radar.models import (
    BusinessDomain,
    ConceptAnalysis,
)
from enterprise_concept_radar.tools import (
    load_policy_directory,
)


def build_test_analysis() -> ConceptAnalysis:
    """创建测试用概念分析。"""
    return ConceptAnalysis(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        explanation_draft="多个用户参与的绿电直连安排。",
        source_facts=[
            "输入材料提出探索多用户绿电直连协同机制。"
        ],
        rule_judgements=[
            "规则系统将其识别为新增说法。"
        ],
        model_inferences=[
            "该机制可能涉及跨用户计量协调。"
        ],
        related_term_comparison=[
            "它与绿电直连相关，但增加了多用户协同场景。"
        ],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        verification_actions=[
            "检索真实政策原文。"
        ],
        confidence=0.8,
    )


def build_fake_response(
    reverse_domains: bool = False,
    include_all_domains: bool = True,
    include_warning: bool = True,
) -> str:
    """创建业务影响模拟响应。"""
    domains = list(BusinessDomain)

    if not include_all_domains:
        domains = domains[:-1]

    if reverse_domains:
        domains.reverse()

    domain_impacts = [
        {
            "domain": domain.value,
            "impact_level": "中",
            "impact_summary": (
                f"该概念可能影响{domain.value}相关规则。"
            ),
            "affected_processes": [
                f"{domain.value}业务流程"
            ],
            "risks": [
                "责任边界仍需核验"
            ],
            "opportunities": [
                "促进跨专业协同"
            ],
            "recommended_actions": [
                "组织专题研究"
            ],
            "evidence_basis": [
                "[政策原文事实] 输入材料提出探索协同机制",
                "[模型推断] 可能影响现有业务规则",
            ],
        }
        for domain in domains
    ]

    uncertainties = []

    if include_warning:
        uncertainties.append(
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        )

    data = {
        "term": "模型错误术语",
        "source_document_id": "wrong-document-id",
        "source_is_simulated": False,
        "overall_summary": (
            "该概念可能对多个电网专业产生协同影响。"
        ),
        "domain_impacts": domain_impacts,
        "cross_domain_issues": [
            "规划、市场和计量专业需要协同"
        ],
        "governance_tasks": [
            "建立概念词条并关联业务流程"
        ],
        "uncertainties": uncertainties,
        "confidence": 0.76,
    }

    return json.dumps(
        data,
        ensure_ascii=False,
    )


def test_business_impact_uses_local_identity_fields() -> None:
    """概念和来源信息应以本地数据为准。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            assert "规划建设" in input_text
            assert "知识治理" in input_text
            assert kwargs["max_tokens"] == 3200
            return build_fake_response()

    assessment = assess_business_impact(
        document=document,
        analysis=analysis,
        agent=FakeAgent(),
    )

    assert assessment.term == "多用户绿电直连"
    assert (
        assessment.source_document_id
        == "demo-policy-2026-001"
    )
    assert assessment.source_is_simulated is True
    assert len(assessment.domain_impacts) == 6


def test_missing_business_domain_is_rejected() -> None:
    """缺少任一业务领域时应拒绝模型结果。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()

    with pytest.raises(
        BusinessImpactError,
        match="业务影响领域不完整",
    ):
        parse_business_impact_response(
            raw_response=build_fake_response(
                include_all_domains=False
            ),
            document=document,
            analysis=analysis,
        )


def test_simulation_warning_is_added_locally() -> None:
    """模拟来源警告缺失时应由本地程序补充。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()

    assessment = parse_business_impact_response(
        raw_response=build_fake_response(
            include_warning=False
        ),
        document=document,
        analysis=analysis,
    )

    assert (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
        in assessment.uncertainties
    )


def test_business_domains_are_returned_in_fixed_order() -> None:
    """模型输出顺序不同也应整理为固定业务顺序。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()

    assessment = parse_business_impact_response(
        raw_response=build_fake_response(
            reverse_domains=True
        ),
        document=document,
        analysis=analysis,
    )

    actual_domains = [
        impact.domain
        for impact in assessment.domain_impacts
    ]

    assert actual_domains == list(BusinessDomain)