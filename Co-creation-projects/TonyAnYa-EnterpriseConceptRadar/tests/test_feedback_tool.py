"""测试回答反馈的记录与聚合工具。"""

from enterprise_concept_radar.models import (
    FeedbackAction,
    FeedbackRating,
)
from enterprise_concept_radar.tools import (
    append_feedback_event,
    calculate_feedback_summary,
    create_feedback_event,
    load_feedback_events,
)


def test_feedback_events_can_be_saved_and_loaded(
    tmp_path,
) -> None:
    """反馈事件应能通过 JSONL 保存和读取。"""
    path = tmp_path / "feedback.jsonl"

    event = create_feedback_event(
        answer_id="answer-a",
        question="测试问题",
        rating=FeedbackRating.PROFESSIONAL,
    )

    append_feedback_event(
        event=event,
        path=path,
    )

    loaded = load_feedback_events(
        path=path,
    )

    assert len(loaded) == 1
    assert loaded[0].event_id == event.event_id
    assert loaded[0].rating == FeedbackRating.PROFESSIONAL


def test_feedback_events_can_be_filtered(
    tmp_path,
) -> None:
    """读取反馈时应能按回答 ID 过滤。"""
    path = tmp_path / "feedback.jsonl"

    for answer_id in ("answer-a", "answer-b"):
        append_feedback_event(
            event=create_feedback_event(
                answer_id=answer_id,
                action=FeedbackAction.COPY,
            ),
            path=path,
        )

    loaded = load_feedback_events(
        path=path,
        answer_id="answer-b",
    )

    assert len(loaded) == 1
    assert loaded[0].answer_id == "answer-b"


def test_feedback_summary_combines_rating_and_action() -> None:
    """评价和行为同时存在时应按七三权重计算。"""
    events = [
        create_feedback_event(
            answer_id="answer-a",
            rating=FeedbackRating.AVERAGE,
        ),
        create_feedback_event(
            answer_id="answer-a",
            action=FeedbackAction.COPY,
        ),
    ]

    summary = calculate_feedback_summary(
        answer_id="answer-a",
        events=events,
    )

    assert summary.rating_score == 60
    assert summary.action_score == 80
    assert summary.user_feedback_score == 66


def test_no_feedback_uses_neutral_score() -> None:
    """没有反馈时应使用中性默认分 50。"""
    summary = calculate_feedback_summary(
        answer_id="answer-a",
        events=[],
    )

    assert summary.total_events == 0
    assert summary.user_feedback_score == 50