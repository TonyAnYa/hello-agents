"""根据分析结果与用户反馈生成知识治理任务。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    AnswerFeedbackEvent,
    BusinessImpactAssessment,
    FeedbackAction,
    FeedbackRating,
    GovernanceTask,
    GovernanceTaskBatch,
    GovernanceTaskPriority,
    GovernanceTaskType,
)


class GovernanceTaskError(RuntimeError):
    """知识治理任务生成或存储失败。"""

def infer_governance_task_type(
    text: str,
) -> GovernanceTaskType:
    """根据任务描述推断治理任务类型。"""
    normalized_text = text.strip()

    # 回答复核应使用明确的质量问题关键词，
    # 避免普通治理建议被错误归入回答质量复核。
    if any(
        keyword in normalized_text
        for keyword in (
            "复核回答",
            "回答质量",
            "证据引用",
            "不匹配",
            "用户评价",
        )
    ):
        return GovernanceTaskType.ANSWER_REVIEW

    if any(
        keyword in normalized_text
        for keyword in (
            "词条",
            "条目",
            "概念库",
            "知识库",
            "概念跟踪",
            "概念演变",
        )
    ):
        return GovernanceTaskType.CONCEPT_ENTRY

    if any(
        keyword in normalized_text
        for keyword in (
            "核验",
            "溯源",
            "政策来源",
            "政策原文",
            "发布机构",
            "文号",
        )
    ):
        return GovernanceTaskType.SOURCE_VERIFICATION

    if any(
        keyword in normalized_text
        for keyword in (
            "标准问答",
            "标准答案",
            "问答库",
            "沉淀为问答",
        )
    ):
        return GovernanceTaskType.STANDARD_QA

    if any(
        keyword in normalized_text
        for keyword in (
            "业务规则",
            "业务流程",
            "映射关系",
            "跨部门",
            "跨专业",
            "研讨会",
            "各领域",
        )
    ):
        return GovernanceTaskType.BUSINESS_RULE_MAPPING

    # 无法明确分类时保留人工复核入口。
    return GovernanceTaskType.ANSWER_REVIEW

def build_governance_task_batch(
    impact_assessment: BusinessImpactAssessment,
    feedback_events: Iterable[AnswerFeedbackEvent] = (),
) -> GovernanceTaskBatch:
    """将业务影响、疑点和反馈转化为治理任务。"""
    tasks: list[GovernanceTask] = []
    feedback_list = list(feedback_events)

    for task_text in impact_assessment.governance_tasks:
        task_type = infer_governance_task_type(
            task_text
        )

        tasks.append(
            GovernanceTask(
                term=impact_assessment.term,
                source_document_id=(
                    impact_assessment.source_document_id
                ),
                task_type=task_type,
                priority=GovernanceTaskPriority.MEDIUM,
                title=task_text[:120],
                description=task_text,
                trigger="业务影响评估提出知识治理建议",
                evidence_basis=[
                    impact_assessment.overall_summary,
                ],
                recommended_actions=[
                    task_text,
                ],
            )
        )

    if impact_assessment.uncertainties:
        tasks.append(
            GovernanceTask(
                term=impact_assessment.term,
                source_document_id=(
                    impact_assessment.source_document_id
                ),
                task_type=(
                    GovernanceTaskType.SOURCE_VERIFICATION
                ),
                priority=(
                    GovernanceTaskPriority.HIGH
                    if impact_assessment.source_is_simulated
                    else GovernanceTaskPriority.MEDIUM
                ),
                title=(
                    f"核验“{impact_assessment.term}”"
                    "的政策依据"
                ),
                description=(
                    "核验当前分析中尚未确认的政策来源、"
                    "定义、适用范围和实施条件。"
                ),
                trigger="业务影响评估存在不确定事项",
                evidence_basis=list(
                    impact_assessment.uncertainties
                ),
                recommended_actions=[
                    "检索并核验正式政策原文",
                    "记录发布机构、文号和发布日期",
                    "确认概念定义和适用范围",
                ],
            )
        )

    events_by_answer: dict[
        str,
        list[AnswerFeedbackEvent],
    ] = {}

    for event in feedback_list:
        events_by_answer.setdefault(
            event.answer_id,
            [],
        ).append(event)

    for answer_id, answer_events in events_by_answer.items():
        has_mismatch = any(
            event.rating == FeedbackRating.MISMATCH
            for event in answer_events
        )
        has_average = any(
            event.rating == FeedbackRating.AVERAGE
            for event in answer_events
        )
        has_adopt = any(
            event.action == FeedbackAction.ADOPT
            for event in answer_events
        )
        has_copy = any(
            event.action == FeedbackAction.COPY
            for event in answer_events
        )

        if has_mismatch or has_average:
            priority = (
                GovernanceTaskPriority.HIGH
                if has_mismatch
                else GovernanceTaskPriority.MEDIUM
            )
            rating_text = (
                "不匹配"
                if has_mismatch
                else "一般"
            )

            tasks.append(
                GovernanceTask(
                    term=impact_assessment.term,
                    source_document_id=(
                        impact_assessment.source_document_id
                    ),
                    task_type=(
                        GovernanceTaskType.ANSWER_REVIEW
                    ),
                    priority=priority,
                    title=f"复核回答 {answer_id}",
                    description=(
                        f"用户将回答评价为“{rating_text}”，"
                        "需要复核概念解释、业务影响和证据引用。"
                    ),
                    trigger=f"用户评价：{rating_text}",
                    related_answer_id=answer_id,
                    evidence_basis=[
                        event.event_id
                        for event in answer_events
                        if event.rating is not None
                    ],
                    recommended_actions=[
                        "检查回答是否准确理解用户问题",
                        "核验回答引用的政策依据",
                        "补充缺失的业务影响和限制说明",
                    ],
                )
            )

        if has_adopt or has_copy:
            priority = (
                GovernanceTaskPriority.MEDIUM
                if has_adopt
                else GovernanceTaskPriority.LOW
            )
            action_text = (
                "采纳"
                if has_adopt
                else "复制"
            )

            tasks.append(
                GovernanceTask(
                    term=impact_assessment.term,
                    source_document_id=(
                        impact_assessment.source_document_id
                    ),
                    task_type=(
                        GovernanceTaskType.STANDARD_QA
                    ),
                    priority=priority,
                    title=f"评估回答 {answer_id} 的沉淀价值",
                    description=(
                        f"用户对该回答执行了“{action_text}”行为，"
                        "可评估是否沉淀为标准问答草稿。"
                    ),
                    trigger=f"用户行为：{action_text}",
                    related_answer_id=answer_id,
                    evidence_basis=[
                        event.event_id
                        for event in answer_events
                        if event.action is not None
                    ],
                    recommended_actions=[
                        "由专业人员复核回答内容",
                        "补充正式政策来源和版本信息",
                        "审核通过后纳入标准问答库",
                    ],
                )
            )

    if not tasks:
        tasks.append(
            GovernanceTask(
                term=impact_assessment.term,
                source_document_id=(
                    impact_assessment.source_document_id
                ),
                task_type=(
                    GovernanceTaskType.BUSINESS_RULE_MAPPING
                ),
                priority=GovernanceTaskPriority.LOW,
                title=(
                    f"复核“{impact_assessment.term}”"
                    "的业务规则映射"
                ),
                description=(
                    "当前未形成明确治理任务，"
                    "建议人工复核概念与业务流程的映射关系。"
                ),
                trigger="默认知识治理检查",
                evidence_basis=[
                    impact_assessment.overall_summary,
                ],
                recommended_actions=[
                    "确认是否需要建立概念词条",
                    "确认是否需要关联业务流程",
                ],
            )
        )

    return GovernanceTaskBatch(
        term=impact_assessment.term,
        source_document_id=(
            impact_assessment.source_document_id
        ),
        tasks=tasks,
        generated_from_feedback=any(
            task.related_answer_id is not None
            for task in tasks
        ),
    )


def default_governance_task_path() -> Path:
    """返回默认知识治理任务文件路径。"""
    return (
        RUNTIME_DATA_DIR
        / "governance"
        / "governance_tasks.json"
    )


def save_governance_task_batch(
    batch: GovernanceTaskBatch,
    path: str | Path | None = None,
) -> Path:
    """保存知识治理任务批次。"""
    target = (
        Path(path)
        if path is not None
        else default_governance_task_path()
    )

    try:
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        target.write_text(
            batch.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise GovernanceTaskError(
            f"无法保存知识治理任务：{target}；{exc}"
        ) from exc

    return target


def load_governance_task_batch(
    path: str | Path | None = None,
) -> GovernanceTaskBatch:
    """读取知识治理任务批次。"""
    target = (
        Path(path)
        if path is not None
        else default_governance_task_path()
    )

    if not target.is_file():
        raise GovernanceTaskError(
            f"知识治理任务文件不存在：{target}"
        )

    try:
        content = target.read_text(
            encoding="utf-8",
        )
        return GovernanceTaskBatch.model_validate_json(
            content
        )
    except OSError as exc:
        raise GovernanceTaskError(
            f"无法读取知识治理任务：{target}；{exc}"
        ) from exc
    except (ValidationError, ValueError) as exc:
        raise GovernanceTaskError(
            f"知识治理任务文件内容无效：{target}；{exc}"
        ) from exc