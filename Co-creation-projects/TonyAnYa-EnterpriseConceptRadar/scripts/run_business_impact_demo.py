"""运行 BusinessImpactAgent 在线演示。"""

from enterprise_concept_radar.agents import (
    analyze_concept,
    assess_business_impact,
    save_business_impact,
    save_concept_analysis,
)
from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
)
from enterprise_concept_radar.models import (
    ConceptAnalysis,
)
from enterprise_concept_radar.workflow import (
    run_demo_concept_discovery,
)


def load_or_create_concept_analysis(
    document,
    candidate,
) -> ConceptAnalysis:
    """优先读取已有概念分析，否则在线生成。"""
    analysis_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_direct.json"
    )

    if analysis_path.is_file():
        print("读取已有 ConceptAnalysis：", analysis_path)

        return ConceptAnalysis.model_validate_json(
            analysis_path.read_text(
                encoding="utf-8",
            )
        )

    print("未找到已有概念分析，正在在线生成……")

    analysis = analyze_concept(
        document=document,
        candidate=candidate,
    )

    save_concept_analysis(
        analysis=analysis,
        output_path=analysis_path,
    )

    return analysis


def main() -> None:
    """运行业务影响分析演示。"""
    discovery_result = run_demo_concept_discovery()

    candidate = next(
        item
        for item in discovery_result.candidates
        if item.term == "多用户绿电直连"
    )

    analysis = load_or_create_concept_analysis(
        document=discovery_result.document,
        candidate=candidate,
    )

    print("正在调用 BusinessImpactAgent……")

    assessment = assess_business_impact(
        document=discovery_result.document,
        analysis=analysis,
    )

    output_path = save_business_impact(
        assessment=assessment,
        output_path=(
            CONCEPT_CARD_DIR
            / "demo_multi_user_green_power_business_impact.json"
        ),
    )

    print("=" * 60)
    print("广东电网业务影响分析完成")
    print("=" * 60)
    print("概念：", assessment.term)
    print("总体摘要：", assessment.overall_summary)
    print("业务领域数量：", len(assessment.domain_impacts))

    for impact in assessment.domain_impacts:
        print(
            f"- {impact.domain.value} | "
            f"影响程度：{impact.impact_level.value}"
        )

    print("跨专业事项：", len(assessment.cross_domain_issues), "项")
    print("知识治理任务：", len(assessment.governance_tasks), "项")
    print("不确定事项：", len(assessment.uncertainties), "项")
    print("置信度：", assessment.confidence)
    print("结果文件：", output_path)


if __name__ == "__main__":
    main()