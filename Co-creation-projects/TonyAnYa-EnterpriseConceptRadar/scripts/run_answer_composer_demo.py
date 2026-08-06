"""运行 AnswerComposerAgent 在线演示。"""

from pathlib import Path

from enterprise_concept_radar.agents import (
    compose_answer_package,
    save_answer_package,
)
from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
)
from enterprise_concept_radar.models import (
    BusinessImpactAssessment,
    ConceptAnalysis,
)
from enterprise_concept_radar.workflow import (
    run_demo_concept_discovery,
)


def load_required_result(
    path: Path,
    model_type,
):
    """读取前序工作流生成的结构化结果。"""
    if not path.is_file():
        raise SystemExit(
            f"缺少前序结果文件：{path}"
        )

    return model_type.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    """生成管理摘要型和专业分析型两份回答。"""
    discovery_result = run_demo_concept_discovery()

    analysis = load_required_result(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_direct.json",
        ConceptAnalysis,
    )
    impact = load_required_result(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_business_impact.json",
        BusinessImpactAssessment,
    )

    question = (
        "多用户绿电直连是什么意思，"
        "对广东电网有什么影响，下一步建议做什么？"
    )

    print("正在调用 AnswerComposerAgent……")

    package = compose_answer_package(
        question=question,
        document=discovery_result.document,
        analysis=analysis,
        impact_assessment=impact,
    )

    output_path = save_answer_package(
        package=package,
        output_path=(
            CONCEPT_CARD_DIR
            / "demo_multi_user_green_power_answers.json"
        ),
    )

    print("=" * 60)
    print("两份候选回答生成完成")
    print("=" * 60)
    print("问题：", package.question)
    print("概念：", package.term)

    for candidate in package.candidates:
        print()
        print(
            f"[{candidate.style.value}] "
            f"{candidate.title}"
        )
        print(candidate.content)
        print(
            "行动建议：",
            len(candidate.action_items),
            "项",
        )
        print(
            "限制说明：",
            len(candidate.caveats),
            "项",
        )

    print()
    print("结果文件：", output_path)


if __name__ == "__main__":
    main()