"""运行两份候选回答的自动评分与推荐演示。"""

from pathlib import Path

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
)
from enterprise_concept_radar.models import (
    AnswerPackage,
    BusinessImpactAssessment,
)
from enterprise_concept_radar.scoring import (
    rank_answer_package,
)


def load_json_model(
    path: Path,
    model_type,
):
    """从 JSON 文件读取 Pydantic 模型。"""
    if not path.is_file():
        raise SystemExit(
            f"缺少前序结果文件：{path}"
        )

    return model_type.model_validate_json(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    """对两份候选回答评分并输出推荐结果。"""
    answer_package = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_answers.json",
        AnswerPackage,
    )
    impact_assessment = load_json_model(
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_business_impact.json",
        BusinessImpactAssessment,
    )

    result = rank_answer_package(
        package=answer_package,
        impact_assessment=impact_assessment,
    )

    output_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_answer_ranking.json"
    )

    output_path.write_text(
        result.model_dump_json(
            indent=2,
            exclude_computed_fields=True,
        ),
        encoding="utf-8",
    )

    print("=" * 60)
    print("候选回答评分完成")
    print("=" * 60)

    for evaluation in result.evaluations:
        print()
        print("回答 ID：", evaluation.answer_id)
        print("语义相关性：", evaluation.semantic_relevance)
        print("关键词覆盖：", evaluation.keyword_coverage)
        print("权威依据：", evaluation.authority_score)
        print("时效性：", evaluation.timeliness_score)
        print("业务关联度：", evaluation.business_relevance)
        print("可操作性：", evaluation.actionability_score)
        print("用户反馈：", evaluation.user_feedback_score)
        print("总分：", evaluation.total_score)

    print()
    print("推荐回答：", result.recommended_answer_id)
    print("推荐理由：", result.recommendation_reason)
    print("结果文件：", output_path)


if __name__ == "__main__":
    main()