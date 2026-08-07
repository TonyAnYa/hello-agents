"""从最近一次智能简报中选择回答并记录用户反馈。"""

from __future__ import annotations

from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
)
from enterprise_concept_radar.intelligence_pipeline import (
    PolicyIntelligenceRun,
)
from enterprise_concept_radar.models import (
    FeedbackAction,
    FeedbackRating,
)
from enterprise_concept_radar.output_paths import (
    resolve_output_directory,
)
from enterprise_concept_radar.tools.feedback import (
    append_feedback_event,
    create_feedback_event,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
)


class FeedbackWorkflowError(RuntimeError):
    """最近结果读取、回答选择或反馈记录失败。"""


class FeedbackAnswerOption(BaseModel):
    """可供用户评价的一份候选回答。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    answer_id: str = Field(
        min_length=1,
    )
    question: str = Field(
        min_length=1,
    )
    term: str = Field(
        min_length=1,
    )
    style: str = Field(
        min_length=1,
    )
    title: str = Field(
        min_length=1,
    )
    content_preview: str = Field(
        min_length=1,
    )
    recommended: bool


def latest_intelligence_path(
    *,
    task: TrackingTask,
    project_root: str | Path = PROJECT_ROOT,
) -> Path:
    """返回任务最近一次智能分析 JSON 路径。"""
    output_root = resolve_output_directory(
        task.output_directory,
        project_root=project_root,
    )

    return (
        output_root
        / task.task_id
        / "latest"
        / "intelligence_run.json"
    )


def load_latest_intelligence_run(
    *,
    task: TrackingTask,
    project_root: str | Path = PROJECT_ROOT,
) -> PolicyIntelligenceRun:
    """读取最近一次成功运行的完整智能分析结果。"""
    path = latest_intelligence_path(
        task=task,
        project_root=project_root,
    )

    if not path.is_file():
        raise FeedbackWorkflowError(
            "尚未找到可评价的智能分析结果："
            f"{path}"
        )

    try:
        return PolicyIntelligenceRun.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise FeedbackWorkflowError(
            f"最近智能分析结果无效：{path}；{exc}"
        ) from exc


def build_feedback_options(
    run: PolicyIntelligenceRun,
) -> list[FeedbackAnswerOption]:
    """列出运行结果中的全部候选回答。"""
    options: list[FeedbackAnswerOption] = []

    for item in run.intelligence_items:
        recommended_id = (
            item.feedback_ranking
            .ranking
            .recommended_answer_id
        )

        for candidate in (
            item.answer_package.candidates
        ):
            preview = " ".join(
                candidate.content.split()
            )[:160]

            options.append(
                FeedbackAnswerOption(
                    answer_id=(
                        candidate.answer_id
                    ),
                    question=(
                        item.answer_package.question
                    ),
                    term=item.candidate.term,
                    style=candidate.style.value,
                    title=candidate.title,
                    content_preview=preview,
                    recommended=(
                        candidate.answer_id
                        == recommended_id
                    ),
                )
            )

    return options


def find_feedback_option(
    *,
    options: list[FeedbackAnswerOption],
    answer_id: str,
) -> FeedbackAnswerOption:
    """按稳定回答 ID 查找可评价回答。"""
    for option in options:
        if option.answer_id == answer_id:
            return option

    raise FeedbackWorkflowError(
        f"最近结果中不存在回答：{answer_id}"
    )


def record_feedback_for_option(
    *,
    option: FeedbackAnswerOption,
    rating: FeedbackRating | None = None,
    action: FeedbackAction | None = None,
    comment: str | None = None,
    feedback_path: str | Path | None = None,
) -> Path:
    """创建并追加一条用户反馈。"""
    try:
        event = create_feedback_event(
            answer_id=option.answer_id,
            question=option.question,
            rating=rating,
            action=action,
            comment=comment,
        )

        return append_feedback_event(
            event=event,
            path=feedback_path,
        )
    except Exception as exc:
        raise FeedbackWorkflowError(
            "无法记录用户反馈："
            f"{type(exc).__name__}: {exc}"
        ) from exc
