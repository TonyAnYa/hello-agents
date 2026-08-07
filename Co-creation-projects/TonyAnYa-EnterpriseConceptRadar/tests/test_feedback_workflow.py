"""测试用户反馈选择和本地持久化。"""

import pytest

from enterprise_concept_radar.feedback_workflow import (
    FeedbackAnswerOption,
    FeedbackWorkflowError,
    find_feedback_option,
    record_feedback_for_option,
)
from enterprise_concept_radar.models import (
    FeedbackAction,
    FeedbackRating,
)
from enterprise_concept_radar.tools.feedback import (
    load_feedback_events,
)


def build_option() -> FeedbackAnswerOption:
    """创建一个可评价回答。"""
    return FeedbackAnswerOption(
        answer_id="answer-stable-id",
        question="该政策有什么影响？",
        term="多主体绿电直连",
        style="管理摘要型",
        title="管理摘要",
        content_preview="建议开展交易规则专题评估。",
        recommended=True,
    )


def test_feedback_is_saved_to_jsonl(
    tmp_path,
) -> None:
    """评价和采纳行为应写入反馈文件。"""
    path = tmp_path / "feedback.jsonl"
    record_feedback_for_option(
        option=build_option(),
        rating=FeedbackRating.PROFESSIONAL,
        action=FeedbackAction.ADOPT,
        comment="可直接用于专题研讨。",
        feedback_path=path,
    )
    events = load_feedback_events(path)

    assert len(events) == 1
    assert events[0].answer_id == (
        "answer-stable-id"
    )
    assert events[0].rating == (
        FeedbackRating.PROFESSIONAL
    )
    assert events[0].action == (
        FeedbackAction.ADOPT
    )


def test_feedback_requires_a_signal(
    tmp_path,
) -> None:
    """只有评论而没有评价或行为时应拒绝。"""
    with pytest.raises(
        FeedbackWorkflowError,
        match="无法记录",
    ):
        record_feedback_for_option(
            option=build_option(),
            comment="只有文字",
            feedback_path=(
                tmp_path / "feedback.jsonl"
            ),
        )


def test_missing_answer_id_is_rejected() -> None:
    """不得为最近结果中不存在的回答记录反馈。"""
    with pytest.raises(
        FeedbackWorkflowError,
        match="不存在回答",
    ):
        find_feedback_option(
            options=[build_option()],
            answer_id="missing-answer",
        )
