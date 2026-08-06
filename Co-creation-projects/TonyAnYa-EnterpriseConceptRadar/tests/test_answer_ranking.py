"""测试候选回答自动排名。"""

import pytest

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerStyle,
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    ImpactLevel,
)
from enterprise_concept_radar.scoring import (
    AnswerRankingError,
    count_covered_business_domains,
    rank_answer_package,
)


def build_impact() -> BusinessImpactAssessment:
    """创建六领域业务影响评估。"""
    return BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="可能影响多个业务领域。",
        domain_impacts=[
            BusinessDomainImpact(
                domain=domain,
                impact_level=ImpactLevel.MEDIUM,
                impact_summary=f"可能影响{domain.value}。",
            )
            for domain in BusinessDomain
        ],
        confidence=0.8,
    )


def build_package() -> AnswerPackage:
    """创建两份覆盖程度不同的候选回答。"""
    executive = AnswerCandidate(
        answer_id="answer-executive",
        style=AnswerStyle.EXECUTIVE_BRIEF,
        title="管理摘要",
        content=(
            "多用户绿电直连可能影响市场交易、"
            "计量结算和安全责任，建议开展专项核验。"
        ),
        evidence_references=[
            "教学模拟政策原文",
        ],
        action_items=[
            "核验真实政策原文",
        ],
        caveats=[
            "当前来源为教学模拟数据",
        ],
    )

    professional = AnswerCandidate(
        answer_id="answer-professional",
        style=AnswerStyle.PROFESSIONAL_ANALYSIS,
        title="专业分析",
        content=(
            "多用户绿电直连可能影响规划建设、调度运行、"
            "市场交易、计量结算、安全责任和知识治理，"
            "建议开展政策核验、业务评估和知识治理。"
        ),
        evidence_references=[
            "教学模拟政策原文",
            "概念分析结果",
            "业务影响评估",
        ],
        action_items=[
            "核验真实政策原文",
            "组织跨专业业务评估",
            "建立概念知识词条",
        ],
        caveats=[
            "当前来源为教学模拟数据",
        ],
    )

    return AnswerPackage(
        question=(
            "多用户绿电直连是什么意思，"
            "对广东电网有什么影响？"
        ),
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        candidates=[
            executive,
            professional,
        ],
    )


def test_business_domain_coverage_can_be_counted() -> None:
    """应统计回答正文明确覆盖的业务领域。"""
    package = build_package()

    assert count_covered_business_domains(
        package.candidates[0]
    ) == 3

    assert count_covered_business_domains(
        package.candidates[1]
    ) == 6


def test_answer_package_can_be_ranked() -> None:
    """专业分析回答覆盖更完整时应获得推荐。"""
    result = rank_answer_package(
        package=build_package(),
        impact_assessment=build_impact(),
    )

    assert len(result.evaluations) == 2
    assert (
        result.recommended_answer_id
        == "answer-professional"
    )
    assert (
        result.evaluations[0].total_score
        >= result.evaluations[1].total_score
    )
    assert "教学模拟来源" in result.recommendation_reason


def test_mismatched_term_is_rejected() -> None:
    """回答包与影响评估术语不一致时应拒绝排名。"""
    impact = build_impact().model_copy(
        update={
            "term": "另一个概念",
        }
    )

    with pytest.raises(
        AnswerRankingError,
        match="term 不一致",
    ):
        rank_answer_package(
            package=build_package(),
            impact_assessment=impact,
        )