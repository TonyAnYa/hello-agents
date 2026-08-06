"""测试广东电网业务影响数据模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    ImpactLevel,
)


def build_domain_impact(
    domain: BusinessDomain,
) -> BusinessDomainImpact:
    """创建一个测试业务影响。"""
    return BusinessDomainImpact(
        domain=domain,
        impact_level=ImpactLevel.MEDIUM,
        impact_summary="可能影响现有业务规则和协同流程。",
        affected_processes=["业务规则维护"],
        risks=["责任边界需要进一步明确"],
        opportunities=["完善跨专业协同机制"],
        recommended_actions=["组织专题研究"],
        evidence_basis=["概念分析草稿中的模型推断"],
    )


def test_business_impact_assessment_can_be_created() -> None:
    """合法的业务影响评估应能通过校验。"""
    assessment = BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="该概念可能影响多个电网业务领域。",
        domain_impacts=[
            build_domain_impact(
                BusinessDomain.PLANNING
            ),
            build_domain_impact(
                BusinessDomain.MARKET
            ),
        ],
        cross_domain_issues=["规划与市场专业需要协同"],
        governance_tasks=["建立概念词条"],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        confidence=0.75,
    )

    assert assessment.term == "多用户绿电直连"
    assert len(assessment.domain_impacts) == 2
    assert assessment.source_is_simulated is True


def test_duplicate_business_domains_are_rejected() -> None:
    """同一领域重复出现时应拒绝数据。"""
    repeated_impact = build_domain_impact(
        BusinessDomain.MARKET
    )

    with pytest.raises(
        ValidationError,
        match="重复业务领域",
    ):
        BusinessImpactAssessment(
            term="测试概念",
            source_document_id="demo-1",
            source_is_simulated=True,
            overall_summary="测试影响。",
            domain_impacts=[
                repeated_impact,
                repeated_impact,
            ],
            confidence=0.5,
        )


def test_invalid_confidence_is_rejected() -> None:
    """置信度必须在 0 到 1 之间。"""
    with pytest.raises(ValidationError):
        BusinessImpactAssessment(
            term="测试概念",
            source_document_id="demo-1",
            source_is_simulated=True,
            overall_summary="测试影响。",
            domain_impacts=[
                build_domain_impact(
                    BusinessDomain.SAFETY
                )
            ],
            confidence=1.5,
        )