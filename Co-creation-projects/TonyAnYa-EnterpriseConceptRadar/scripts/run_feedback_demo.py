"""运行回答反馈记录与聚合演示。"""

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    AnswerRankingResult,
    FeedbackAction,
    FeedbackRating,
)
from enterprise_concept_radar.tools import (
    append_feedback_event,
    calculate_feedback_summary,
    create_feedback_event,
    load_feedback_events,
)


def main() -> None:
    """为当前推荐回答写入两条演示反馈。"""
    ranking_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_answer_ranking.json"
    )

    if not ranking_path.is_file():
        raise SystemExit(
            f"缺少回答排名结果：{ranking_path}"
        )

    ranking = AnswerRankingResult.model_validate_json(
        ranking_path.read_text(encoding="utf-8")
    )
    answer_id = ranking.recommended_answer_id

    feedback_path = (
        RUNTIME_DATA_DIR
        / "feedback"
        / "demo_answer_feedback.jsonl"
    )

    # 仅清理演示文件，不影响正式反馈记录。
    if feedback_path.is_file():
        feedback_path.unlink()

    events = [
        create_feedback_event(
            answer_id=answer_id,
            question=ranking.question,
            rating=FeedbackRating.PROFESSIONAL,
            comment="演示：回答内容专业。",
        ),
        create_feedback_event(
            answer_id=answer_id,
            question=ranking.question,
            action=FeedbackAction.ADOPT,
            comment="演示：用户采纳该回答。",
        ),
    ]

    for event in events:
        append_feedback_event(
            event=event,
            path=feedback_path,
        )

    loaded_events = load_feedback_events(
        path=feedback_path,
    )
    summary = calculate_feedback_summary(
        answer_id=answer_id,
        events=loaded_events,
    )

    summary_path = (
        RUNTIME_DATA_DIR
        / "feedback"
        / "demo_answer_feedback_summary.json"
    )
    summary_path.write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("用户反馈演示完成")
    print("=" * 60)
    print("回答 ID：", summary.answer_id)
    print("反馈事件：", summary.total_events)
    print("评价统计：", summary.rating_counts)
    print("行为统计：", summary.action_counts)
    print("评价得分：", summary.rating_score)
    print("行为得分：", summary.action_score)
    print("用户反馈总分：", summary.user_feedback_score)
    print("反馈文件：", feedback_path)
    print("汇总文件：", summary_path)


if __name__ == "__main__":
    main()