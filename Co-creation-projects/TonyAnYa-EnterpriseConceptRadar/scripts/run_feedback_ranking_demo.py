"""使用历史反馈重新计算候选回答排名。"""

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    AnswerPackage,
    BusinessImpactAssessment,
)
from enterprise_concept_radar.scoring import (
    rank_answer_package_with_feedback,
)
from enterprise_concept_radar.tools import (
    load_feedback_events,
)


def main() -> None:
    """读取演示反馈并重新计算回答排名。"""
    answer_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_answers.json"
    )
    impact_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_business_impact.json"
    )
    feedback_path = (
        RUNTIME_DATA_DIR
        / "feedback"
        / "demo_answer_feedback.jsonl"
    )

    for path in (
        answer_path,
        impact_path,
        feedback_path,
    ):
        if not path.is_file():
            raise SystemExit(
                f"缺少演示文件：{path}"
            )

    package = AnswerPackage.model_validate_json(
        answer_path.read_text(encoding="utf-8")
    )
    impact = BusinessImpactAssessment.model_validate_json(
        impact_path.read_text(encoding="utf-8")
    )
    events = load_feedback_events(
        path=feedback_path,
    )

    result = rank_answer_package_with_feedback(
        package=package,
        impact_assessment=impact,
        events=events,
    )

    output_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_feedback_ranking.json"
    )
    output_path.write_text(
        result.model_dump_json(
            indent=2,
            exclude_computed_fields=True,
        ),
        encoding="utf-8",
    )

    print("=" * 60)
    print("反馈感知排名完成")
    print("=" * 60)

    for summary in result.feedback_summaries:
        print()
        print("回答 ID：", summary.answer_id)
        print("反馈事件：", summary.total_events)
        print("用户反馈分：", summary.user_feedback_score)

    print()
    print("重新评分结果：")

    for evaluation in result.ranking.evaluations:
        print(
            f"- {evaluation.answer_id} | "
            f"反馈分：{evaluation.user_feedback_score} | "
            f"总分：{evaluation.total_score}"
        )

    print()
    print(
        "推荐回答：",
        result.ranking.recommended_answer_id,
    )
    print(
        "推荐理由：",
        result.ranking.recommendation_reason,
    )
    print("结果文件：", output_path)


if __name__ == "__main__":
    main()