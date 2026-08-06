"""运行 ConceptAnalysisAgent 在线演示。"""

from enterprise_concept_radar.agents import (
    analyze_concept,
    save_concept_analysis,
)
from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
)
from enterprise_concept_radar.workflow import (
    run_demo_concept_discovery,
)


def main() -> None:
    """分析教学样本中的多用户绿电直连概念。"""
    discovery_result = run_demo_concept_discovery()

    candidate = next(
        item
        for item in discovery_result.candidates
        if item.term == "多用户绿电直连"
    )

    print("正在调用 ConceptAnalysisAgent……")

    analysis = analyze_concept(
        document=discovery_result.document,
        candidate=candidate,
    )

    output_path = save_concept_analysis(
        analysis=analysis,
        output_path=(
            CONCEPT_CARD_DIR
            / "demo_multi_user_green_power_direct.json"
        ),
    )

    print("=" * 60)
    print("概念分析完成")
    print("=" * 60)
    print("概念：", analysis.term)
    print("解释草稿：", analysis.explanation_draft)
    print("来源事实：", len(analysis.source_facts), "条")
    print("规则判断：", len(analysis.rule_judgements), "条")
    print("模型推断：", len(analysis.model_inferences), "条")
    print("不确定事项：", len(analysis.uncertainties), "条")
    print("置信度：", analysis.confidence)
    print("结果文件：", output_path)


if __name__ == "__main__":
    main()