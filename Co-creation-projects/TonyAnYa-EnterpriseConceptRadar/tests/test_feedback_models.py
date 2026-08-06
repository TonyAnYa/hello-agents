"""测试回答反馈数据模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    AnswerFeedbackEvent,
    FeedbackAction,
    FeedbackRating,
)


def test_feedback_event_accepts_rating() -> None:
    """包含评价信号的反馈应通过校验。"""
    event = AnswerFeedbackEvent(
        answer_id="answer-a",
        rating=FeedbackRating.PROFESSIONAL,
    )

    assert event.rating == FeedbackRating.PROFESSIONAL
    assert event.event_id


def test_feedback_event_accepts_action() -> None:
    """包含行为信号的反馈应通过校验。"""
    event = AnswerFeedbackEvent(
        answer_id="answer-a",
        action=FeedbackAction.ADOPT,
    )

    assert event.action == FeedbackAction.ADOPT


def test_feedback_event_requires_signal() -> None:
    """没有评价或行为的事件应被拒绝。"""
    with pytest.raises(
        ValidationError,
        match="至少包含 rating 或 action",
    ):
        AnswerFeedbackEvent(
            answer_id="answer-a",
            comment="只有文字，没有反馈信号。",
        )