"""生成 EnterpriseConceptRadar 综合演示报告。"""

from pathlib import Path

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    REPORT_DIR,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    AnswerPackage,
    BusinessImpactAssessment,
    ConceptAnalysis,
    FeedbackAwareRankingResult,
    GovernanceTaskBatch,
)
from enterprise_concept_radar.tools import (
    build_integrated_report,
    save_integrated_report,
)


def load_json_model(
    path: Path,
    model_type,
):
    """读取前序工作流生成的 JSON 模型。"""
    if not path.is_file():
        raise SystemExit(
            f"缺少前序结果文件：{path}"
        )

    return model_type.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    """汇总概念、影响、回答、反馈和治理任务。"""
    analysis = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_direct.json",
        ConceptAnalysis,
    )
    impact = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_business_impact.json",
        BusinessImpactAssessment,
    )
    answers = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_answers.json",
        AnswerPackage,
    )
    feedback_ranking = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_feedback_ranking.json",
        FeedbackAwareRankingResult,
    )
    governance = load_json_model(
        RUNTIME_DATA_DIR
        / "governance"
        / "demo_governance_tasks.json",
        GovernanceTaskBatch,
    )

    report = build_integrated_report(
        analysis=analysis,
        impact_assessment=impact,
        answer_package=answers,
        feedback_ranking=feedback_ranking,
        governance_batch=governance,
    )

    output_path = save_integrated_report(
        report=report,
        output_path=(
            REPORT_DIR
            / "demo_enterprise_concept_radar_full_report.md"
        ),
    )

    print("=" * 60)
    print("综合管理报告生成完成")
    print("=" * 60)
    print("概念：", analysis.term)
    print(
        "推荐回答：",
        feedback_ranking.ranking.recommended_answer_id,
    )
    print("业务领域：", len(impact.domain_impacts))
    print("治理任务：", len(governance.tasks))
    print("报告文件：", output_path)


if __name__ == "__main__":
    main()