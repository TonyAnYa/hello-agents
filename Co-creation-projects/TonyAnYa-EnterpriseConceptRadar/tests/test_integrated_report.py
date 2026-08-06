"""测试综合管理报告生成。"""

import pytest

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerStyle,
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    ConceptAnalysis,
    FeedbackAction,
    FeedbackRating,
    ImpactLevel,
)
from enterprise_concept_radar.scoring import (
    rank_answer_package_with_feedback,
)
from enterprise_concept_radar.tools import (
    IntegratedReportError,
    build_governance_task_batch,
    build_integrated_report,
    create_feedback_event,
    save_integrated_report,
)


def build_analysis() -> ConceptAnalysis:
    """创建测试概念分析。"""
    return ConceptAnalysis(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        explanation_draft=(
            "多个用户协同参与绿电直接供应的分析草稿。"
        ),
        source_facts=[
            "输入材料提出探索多用户绿电直连协同机制。"
        ],
        rule_judgements=[
            "规则系统将其识别为新增说法。"
        ],
        model_inferences=[
            "可能涉及多用户计量和责任协调。"
        ],
        related_term_comparison=[
            "与绿电直连相关，但增加多用户场景。"
        ],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        verification_actions=[
            "检索并核验正式政策原文。"
        ],
        confidence=0.8,
    )


def build_impact() -> BusinessImpactAssessment:
    """创建测试业务影响评估。"""
    return BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="可能影响多个电网业务领域。",
        domain_impacts=[
            BusinessDomainImpact(
                domain=domain,
                impact_level=ImpactLevel.MEDIUM,
                impact_summary=f"可能影响{domain.value}。",
                recommended_actions=[
                    f"核验{domain.value}相关规则"
                ],
            )
            for domain in BusinessDomain
        ],
        cross_domain_issues=[
            "需要规划、调度和市场专业协同。"
        ],
        governance_tasks=[
            "建立多用户绿电直连概念词条"
        ],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        confidence=0.8,
    )


def build_answer_package() -> AnswerPackage:
    """创建测试候选回答。"""
    return AnswerPackage(
        question=(
            "多用户绿电直连是什么意思，"
            "对广东电网有什么影响？"
        ),
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        candidates=[
            AnswerCandidate(
                answer_id="answer-executive",
                style=AnswerStyle.EXECUTIVE_BRIEF,
                title="管理摘要",
                content=(
                    "多用户绿电直连可能影响规划建设、"
                    "调度运行、市场交易、计量结算、"
                    "安全责任和知识治理。"
                ),
                evidence_references=["教学模拟政策"],
                action_items=["核验正式政策原文"],
                caveats=["当前为分析草稿"],
            ),
            AnswerCandidate(
                answer_id="answer-professional",
                style=AnswerStyle.PROFESSIONAL_ANALYSIS,
                title="专业分析",
                content=(
                    "多用户绿电直连可能影响规划建设、"
                    "调度运行、市场交易、计量结算、"
                    "安全责任和知识治理，需开展跨专业评估。"
                ),
                evidence_references=[
                    "教学模拟政策",
                    "概念分析",
                ],
                action_items=[
                    "核验正式政策原文",
                    "开展跨专业业务评估",
                ],
                caveats=["当前为分析草稿"],
            ),
        ],
    )


def build_report_inputs():
    """创建完整测试输入。"""
    analysis = build_analysis()
    impact = build_impact()
    package = build_answer_package()

    events = [
        create_feedback_event(
            answer_id="answer-executive",
            rating=FeedbackRating.PROFESSIONAL,
        ),
        create_feedback_event(
            answer_id="answer-executive",
            action=FeedbackAction.ADOPT,
        ),
    ]

    ranking = rank_answer_package_with_feedback(
        package=package,
        impact_assessment=impact,
        events=events,
    )
    governance = build_governance_task_batch(
        impact_assessment=impact,
        feedback_events=events,
    )

    return (
        analysis,
        impact,
        package,
        ranking,
        governance,
    )


def test_integrated_report_contains_core_sections() -> None:
    """综合报告应包含核心分析和推荐章节。"""
    (
        analysis,
        impact,
        package,
        ranking,
        governance,
    ) = build_report_inputs()

    report = build_integrated_report(
        analysis=analysis,
        impact_assessment=impact,
        answer_package=package,
        feedback_ranking=ranking,
        governance_batch=governance,
    )

    assert "# 企业大脑：新词新概念追踪综合报告" in report
    assert "广东电网六领域影响评估" in report
    assert "候选回答评分与推荐" in report
    assert "用户反馈汇总" in report
    assert "知识治理任务" in report


def test_integrated_report_contains_recommended_answer() -> None:
    """报告应包含最终推荐回答正文。"""
    (
        analysis,
        impact,
        package,
        ranking,
        governance,
    ) = build_report_inputs()

    report = build_integrated_report(
        analysis=analysis,
        impact_assessment=impact,
        answer_package=package,
        feedback_ranking=ranking,
        governance_batch=governance,
    )

    assert ranking.ranking.recommended_answer_id in report
    assert "推荐回答" in report


def test_integrated_report_contains_simulation_warning() -> None:
    """教学模拟来源必须显示明确声明。"""
    (
        analysis,
        impact,
        package,
        ranking,
        governance,
    ) = build_report_inputs()

    report = build_integrated_report(
        analysis=analysis,
        impact_assessment=impact,
        answer_package=package,
        feedback_ranking=ranking,
        governance_batch=governance,
    )

    assert (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
        in report
    )


def test_integrated_report_rejects_mismatched_term() -> None:
    """不同概念的输入不能被合并为同一报告。"""
    (
        analysis,
        impact,
        package,
        ranking,
        governance,
    ) = build_report_inputs()

    mismatched_analysis = analysis.model_copy(
        update={
            "term": "另一个政策概念",
        }
    )

    with pytest.raises(
        IntegratedReportError,
        match="term 不一致",
    ):
        build_integrated_report(
            analysis=mismatched_analysis,
            impact_assessment=impact,
            answer_package=package,
            feedback_ranking=ranking,
            governance_batch=governance,
        )


def test_integrated_report_can_be_saved(
    tmp_path,
) -> None:
    """综合报告应能保存为 UTF-8 Markdown。"""
    (
        analysis,
        impact,
        package,
        ranking,
        governance,
    ) = build_report_inputs()

    report = build_integrated_report(
        analysis=analysis,
        impact_assessment=impact,
        answer_package=package,
        feedback_ranking=ranking,
        governance_batch=governance,
    )
    path = save_integrated_report(
        report=report,
        output_path=tmp_path / "report.md",
    )

    assert path.is_file()
    assert "多用户绿电直连" in path.read_text(
        encoding="utf-8"
    )