"""用户回答反馈的本地记录与聚合工具。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    AnswerFeedbackEvent,
    AnswerFeedbackSummary,
    FeedbackAction,
    FeedbackRating,
)

RATING_SCORES = {
    FeedbackRating.PROFESSIONAL: 100.0,
    FeedbackRating.AVERAGE: 60.0,
    FeedbackRating.MISMATCH: 0.0,
}

ACTION_SCORES = {
    FeedbackAction.ADOPT: 100.0,
    FeedbackAction.COPY: 80.0,
}


class FeedbackStorageError(RuntimeError):
    """反馈文件读写失败或内容无效。"""


def default_feedback_path() -> Path:
    """返回默认反馈记录文件路径。"""
    return (
        RUNTIME_DATA_DIR
        / "feedback"
        / "answer_feedback.jsonl"
    )


def create_feedback_event(
    answer_id: str,
    question: str | None = None,
    rating: FeedbackRating | None = None,
    action: FeedbackAction | None = None,
    comment: str | None = None,
) -> AnswerFeedbackEvent:
    """创建经过校验的反馈事件。"""
    return AnswerFeedbackEvent(
        answer_id=answer_id,
        question=question,
        rating=rating,
        action=action,
        comment=comment,
    )


def append_feedback_event(
    event: AnswerFeedbackEvent,
    path: str | Path | None = None,
) -> Path:
    """将一条反馈追加到 JSONL 文件。"""
    target = (
        Path(path)
        if path is not None
        else default_feedback_path()
    )

    try:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with target.open(
            "a",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write(event.model_dump_json())
            file.write("\n")
    except OSError as exc:
        raise FeedbackStorageError(
            f"无法写入反馈文件：{target}；{exc}"
        ) from exc

    return target


def load_feedback_events(
    path: str | Path | None = None,
    answer_id: str | None = None,
) -> list[AnswerFeedbackEvent]:
    """读取反馈文件，可按回答 ID 过滤。"""
    target = (
        Path(path)
        if path is not None
        else default_feedback_path()
    )

    if not target.is_file():
        return []

    events: list[AnswerFeedbackEvent] = []

    try:
        lines = target.read_text(
            encoding="utf-8",
        ).splitlines()
    except OSError as exc:
        raise FeedbackStorageError(
            f"无法读取反馈文件：{target}；{exc}"
        ) from exc

    for line_number, line in enumerate(
        lines,
        start=1,
    ):
        if not line.strip():
            continue

        try:
            event = AnswerFeedbackEvent.model_validate_json(
                line
            )
        except (ValidationError, ValueError) as exc:
            raise FeedbackStorageError(
                f"反馈文件第 {line_number} 行无效：{exc}"
            ) from exc

        if answer_id is None or event.answer_id == answer_id:
            events.append(event)

    return events


def average_score(
    values: list[float],
) -> float | None:
    """计算平均分，无数据时返回 None。"""
    if not values:
        return None

    return round(
        sum(values) / len(values),
        2,
    )


def calculate_feedback_summary(
    answer_id: str,
    events: Iterable[AnswerFeedbackEvent],
) -> AnswerFeedbackSummary:
    """聚合一个回答的反馈并计算反馈得分。

    评分规则：

    - 专业：100
    - 一般：60
    - 不匹配：0
    - 采纳：100
    - 复制：80
    - 同时存在评价和行为时，评价占 70%，行为占 30%
    - 尚无反馈时使用中性默认值 50
    """
    matching_events = [
        event
        for event in events
        if event.answer_id == answer_id
    ]

    rating_counts = {
        rating.value: sum(
            event.rating == rating
            for event in matching_events
        )
        for rating in FeedbackRating
    }
    action_counts = {
        action.value: sum(
            event.action == action
            for event in matching_events
        )
        for action in FeedbackAction
    }

    rating_values = [
        RATING_SCORES[event.rating]
        for event in matching_events
        if event.rating is not None
    ]
    action_values = [
        ACTION_SCORES[event.action]
        for event in matching_events
        if event.action is not None
    ]

    rating_score = average_score(rating_values)
    action_score = average_score(action_values)

    if rating_score is not None and action_score is not None:
        feedback_score = (
            rating_score * 0.7
            + action_score * 0.3
        )
    elif rating_score is not None:
        feedback_score = rating_score
    elif action_score is not None:
        feedback_score = action_score
    else:
        feedback_score = 50.0

    return AnswerFeedbackSummary(
        answer_id=answer_id,
        total_events=len(matching_events),
        rating_counts=rating_counts,
        action_counts=action_counts,
        rating_score=rating_score,
        action_score=action_score,
        user_feedback_score=round(
            feedback_score,
            2,
        ),
    )