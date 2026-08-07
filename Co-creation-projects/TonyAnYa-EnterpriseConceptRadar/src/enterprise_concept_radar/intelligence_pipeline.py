"""将真实政策串联到完整的新词新概念智能分析链路。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.agents.answer_composer_agent import (
    build_answer_composer_agent,
    compose_answer_package,
)
from enterprise_concept_radar.agents.business_impact_agent import (
    assess_business_impact,
    build_business_impact_agent,
)
from enterprise_concept_radar.agents.concept_analysis_agent import (
    analyze_concept,
    build_concept_analysis_agent,
)
from enterprise_concept_radar.agents.concept_discovery_agent import (
    build_concept_discovery_agent,
    discover_policy_concepts,
)
from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    CONFIG_DIR,
)
from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerFeedbackEvent,
    AnswerPackage,
    BusinessImpactAssessment,
    ConceptAnalysis,
    ConceptBaseline,
    ConceptCandidate,
    FeedbackAwareRankingResult,
    GovernanceTaskBatch,
    PolicyDocument,
)
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
)
from enterprise_concept_radar.scoring import (
    load_concept_baseline,
    rank_answer_package_with_feedback,
)
from enterprise_concept_radar.tools import (
    build_governance_task_batch,
    build_integrated_report,
    load_concept_rules,
    load_feedback_events,
)
from enterprise_concept_radar.tools.concept_extractor import (
    ConceptRules,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
)

MAX_AGENT_DOCUMENT_LENGTH = 36_000


class IntelligencePipelineError(RuntimeError):
    """完整智能分析链路无法执行。"""


class IntelligenceFailure(BaseModel):
    """单个政策或概念在某个分析阶段的失败记录。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    document_id: str = Field(
        min_length=1,
    )
    policy_title: str = Field(
        min_length=1,
    )
    stage: str = Field(
        min_length=1,
    )
    term: str | None = None
    error_type: str = Field(
        min_length=1,
    )
    message: str = Field(
        min_length=1,
    )


class PolicyIntelligenceItem(BaseModel):
    """一个政策概念的完整智能分析结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    intelligence_id: str = Field(
        min_length=1,
    )
    document_id: str = Field(
        min_length=1,
    )
    policy_title: str = Field(
        min_length=1,
    )
    policy_source_name: str = Field(
        min_length=1,
    )
    policy_source_url: str = Field(
        min_length=1,
    )
    candidate: ConceptCandidate
    analysis: ConceptAnalysis
    impact_assessment: BusinessImpactAssessment
    answer_package: AnswerPackage
    feedback_ranking: FeedbackAwareRankingResult
    governance_batch: GovernanceTaskBatch
    timeliness_score: float = Field(
        ge=0,
        le=100,
    )
    integrated_report_markdown: str = Field(
        min_length=1,
    )


class PolicyIntelligenceRun(BaseModel):
    """一次追踪任务的完整智能分析运行结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task_id: str = Field(
        min_length=1,
    )
    collection_run_id: str = Field(
        min_length=1,
    )
    started_at: datetime
    completed_at: datetime
    document_count: int = Field(
        ge=0,
    )
    analyzed_document_count: int = Field(
        ge=0,
    )
    intelligence_items: list[
        PolicyIntelligenceItem
    ] = Field(
        default_factory=list,
    )
    failures: list[IntelligenceFailure] = Field(
        default_factory=list,
    )
    llm_stage_count: int = Field(
        ge=0,
        description=(
            "已启动的 LLM 分析阶段数；"
            "Agent 内部重试可能产生额外底层请求"
        ),
    )


def calculate_timeliness_score(
    *,
    published_date: date,
    reference_date: date,
) -> float:
    """按政策距本次运行日期的天数计算时效性分数。"""
    age_days = (
        reference_date - published_date
    ).days

    if age_days <= 7:
        return 100.0

    if age_days <= 30:
        return 92.0

    if age_days <= 90:
        return 82.0

    if age_days <= 180:
        return 72.0

    if age_days <= 365:
        return 62.0

    return 45.0


def build_stable_answer_id(
    *,
    document_id: str,
    term: str,
    style_value: str,
) -> str:
    """生成跨运行稳定的回答 ID，便于累计历史反馈。"""
    identity = "|".join(
        [
            document_id,
            term,
            style_value,
        ]
    )
    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:20]

    return f"answer-{digest}"


def stabilize_answer_package_ids(
    package: AnswerPackage,
) -> AnswerPackage:
    """使用文档、概念和风格重写模型生成的临时回答 ID。"""
    candidates: list[AnswerCandidate] = []

    for candidate in package.candidates:
        candidates.append(
            candidate.model_copy(
                update={
                    "answer_id": build_stable_answer_id(
                        document_id=(
                            package.source_document_id
                        ),
                        term=package.term,
                        style_value=(
                            candidate.style.value
                        ),
                    )
                }
            )
        )

    return package.model_copy(
        update={
            "candidates": candidates,
        }
    )


def build_intelligence_id(
    *,
    document_id: str,
    term: str,
) -> str:
    """生成一个概念情报项的稳定标识。"""
    digest = hashlib.sha256(
        f"{document_id}|{term}".encode(
            "utf-8"
        )
    ).hexdigest()[:20]

    return f"intelligence-{digest}"


def build_agent_document(
    *,
    document: PolicyDocument,
    candidate: ConceptCandidate,
    maximum_length: int = MAX_AGENT_DOCUMENT_LENGTH,
) -> PolicyDocument:
    """为后续 Agent 构造包含证据句的受控长度正文。"""
    if len(document.content) <= maximum_length:
        return document

    evidence_index = document.content.find(
        candidate.evidence_quote
    )
    head_length = maximum_length // 3
    evidence_length = (
        maximum_length - head_length
    )

    if evidence_index < 0:
        focused_content = document.content[
            :maximum_length
        ]
    else:
        context_start = max(
            0,
            evidence_index
            - evidence_length // 3,
        )
        context_end = min(
            len(document.content),
            context_start + evidence_length,
        )
        focused_content = (
            document.content[:head_length]
            + "\n\n……正文已按模型上下文长度截取……\n\n"
            + document.content[
                context_start:context_end
            ]
        )

    metadata = dict(document.metadata)
    metadata["agent_content_truncated"] = True
    metadata["original_content_length"] = len(
        document.content
    )

    return document.model_copy(
        update={
            "content": focused_content,
            "metadata": metadata,
        }
    )


def _failure(
    *,
    document: PolicyDocument,
    stage: str,
    exc: Exception,
    term: str | None = None,
) -> IntelligenceFailure:
    """将异常转换成可审计失败记录。"""
    return IntelligenceFailure(
        document_id=document.document_id,
        policy_title=document.title,
        stage=stage,
        term=term,
        error_type=type(exc).__name__,
        message=str(exc),
    )


def run_policy_intelligence(
    *,
    task: TrackingTask,
    collection_run: PolicyCollectionRun,
    baseline: ConceptBaseline | None = None,
    rules: ConceptRules | None = None,
    feedback_events: Iterable[
        AnswerFeedbackEvent
    ] | None = None,
    discover_func: Callable[..., list[ConceptCandidate]] = (
        discover_policy_concepts
    ),
    analyze_func: Callable[..., ConceptAnalysis] = (
        analyze_concept
    ),
    impact_func: Callable[
        ..., BusinessImpactAssessment
    ] = assess_business_impact,
    compose_func: Callable[..., AnswerPackage] = (
        compose_answer_package
    ),
    ranking_func: Callable[
        ..., FeedbackAwareRankingResult
    ] = rank_answer_package_with_feedback,
    governance_func: Callable[
        ..., GovernanceTaskBatch
    ] = build_governance_task_batch,
    report_func: Callable[..., str] = (
        build_integrated_report
    ),
    discovery_agent: Any | None = None,
    analysis_agent: Any | None = None,
    impact_agent: Any | None = None,
    answer_agent: Any | None = None,
) -> PolicyIntelligenceRun:
    """对本次新增真实政策运行完整智能分析链路。"""
    started_at = datetime.now(timezone.utc)
    active_baseline = (
        baseline
        if baseline is not None
        else load_concept_baseline(
            BASELINE_DATA_DIR
            / "known_terms.json"
        )
    )
    active_rules = (
        rules
        if rules is not None
        else load_concept_rules(
            CONFIG_DIR
            / "concept_rules.yaml"
        )
    )
    active_feedback = (
        list(feedback_events)
        if feedback_events is not None
        else load_feedback_events()
    )

    if (
        discovery_agent is None
        and discover_func
        is discover_policy_concepts
    ):
        discovery_agent = (
            build_concept_discovery_agent()
        )

    if (
        analysis_agent is None
        and analyze_func is analyze_concept
    ):
        analysis_agent = (
            build_concept_analysis_agent()
        )

    if (
        impact_agent is None
        and impact_func
        is assess_business_impact
    ):
        impact_agent = (
            build_business_impact_agent()
        )

    if (
        answer_agent is None
        and compose_func
        is compose_answer_package
    ):
        answer_agent = (
            build_answer_composer_agent()
        )

    items: list[PolicyIntelligenceItem] = []
    failures: list[IntelligenceFailure] = []
    analyzed_document_ids: set[str] = set()
    llm_stage_count = 0
    reference_date = (
        collection_run.completed_at.date()
    )

    for document in collection_run.documents:
        if (
            len(items)
            >= task.max_intelligence_items_per_run
        ):
            break

        try:
            llm_stage_count += 1
            candidates = discover_func(
                document=document,
                baseline=active_baseline,
                question=task.question,
                focus_keywords=task.keywords,
                maximum_candidates=(
                    task.max_concepts_per_policy
                ),
                minimum_confidence=(
                    task.minimum_concept_confidence
                ),
                minimum_term_length=(
                    active_rules.minimum_term_length
                ),
                ignored_terms=(
                    active_rules.ignored_terms
                ),
                agent=discovery_agent,
            )
        except Exception as exc:
            failures.append(
                _failure(
                    document=document,
                    stage="concept_discovery",
                    exc=exc,
                )
            )
            continue

        for candidate in candidates:
            if (
                len(items)
                >= task.max_intelligence_items_per_run
            ):
                break

            if (
                candidate.novelty_score
                < task.minimum_novelty_score
            ):
                continue

            agent_document = build_agent_document(
                document=document,
                candidate=candidate,
            )

            try:
                llm_stage_count += 1
                analysis = analyze_func(
                    document=agent_document,
                    candidate=candidate,
                    agent=analysis_agent,
                )
            except Exception as exc:
                failures.append(
                    _failure(
                        document=document,
                        stage="concept_analysis",
                        term=candidate.term,
                        exc=exc,
                    )
                )
                continue

            try:
                llm_stage_count += 1
                impact = impact_func(
                    document=agent_document,
                    analysis=analysis,
                    agent=impact_agent,
                )
            except Exception as exc:
                failures.append(
                    _failure(
                        document=document,
                        stage="business_impact",
                        term=candidate.term,
                        exc=exc,
                    )
                )
                continue

            try:
                llm_stage_count += 1
                package = compose_func(
                    question=task.question,
                    document=agent_document,
                    analysis=analysis,
                    impact_assessment=impact,
                    agent=answer_agent,
                )
                package = (
                    stabilize_answer_package_ids(
                        package
                    )
                )
            except Exception as exc:
                failures.append(
                    _failure(
                        document=document,
                        stage="answer_composition",
                        term=candidate.term,
                        exc=exc,
                    )
                )
                continue

            timeliness_score = (
                calculate_timeliness_score(
                    published_date=(
                        document.published_date
                    ),
                    reference_date=reference_date,
                )
            )

            try:
                feedback_ranking = ranking_func(
                    package=package,
                    impact_assessment=impact,
                    events=active_feedback,
                    timeliness_score=(
                        timeliness_score
                    ),
                )
                governance = governance_func(
                    impact_assessment=impact,
                    feedback_events=(
                        active_feedback
                    ),
                )
                integrated_report = report_func(
                    analysis=analysis,
                    impact_assessment=impact,
                    answer_package=package,
                    feedback_ranking=(
                        feedback_ranking
                    ),
                    governance_batch=governance,
                )
            except Exception as exc:
                failures.append(
                    _failure(
                        document=document,
                        stage=(
                            "ranking_governance_report"
                        ),
                        term=candidate.term,
                        exc=exc,
                    )
                )
                continue

            items.append(
                PolicyIntelligenceItem(
                    intelligence_id=(
                        build_intelligence_id(
                            document_id=(
                                document.document_id
                            ),
                            term=candidate.term,
                        )
                    ),
                    document_id=(
                        document.document_id
                    ),
                    policy_title=document.title,
                    policy_source_name=(
                        document.source_name
                    ),
                    policy_source_url=str(
                        document.source_url
                    ),
                    candidate=candidate,
                    analysis=analysis,
                    impact_assessment=impact,
                    answer_package=package,
                    feedback_ranking=(
                        feedback_ranking
                    ),
                    governance_batch=governance,
                    timeliness_score=(
                        timeliness_score
                    ),
                    integrated_report_markdown=(
                        integrated_report
                    ),
                )
            )
            analyzed_document_ids.add(
                document.document_id
            )

    return PolicyIntelligenceRun(
        task_id=task.task_id,
        collection_run_id=(
            collection_run.run_id
        ),
        started_at=started_at,
        completed_at=datetime.now(
            timezone.utc
        ),
        document_count=len(
            collection_run.documents
        ),
        analyzed_document_count=len(
            analyzed_document_ids
        ),
        intelligence_items=items,
        failures=failures,
        llm_stage_count=llm_stage_count,
    )


def build_intelligence_brief_markdown(
    *,
    task: TrackingTask,
    run: PolicyIntelligenceRun,
) -> str:
    """生成一次运行的综合管理简报。"""
    lines = [
        f"# {task.name}：智能分析简报",
        "",
        f"- 任务 ID：`{task.task_id}`",
        f"- 用户问题：{task.question}",
        f"- 新增真实政策：{run.document_count}",
        (
            "- 完成分析的政策："
            f"{run.analyzed_document_count}"
        ),
        (
            "- 完整概念情报项："
            f"{len(run.intelligence_items)}"
        ),
        (
            "- LLM 分析阶段："
            f"{run.llm_stage_count}"
        ),
        f"- 分析异常：{len(run.failures)}",
        "",
    ]

    if not run.intelligence_items:
        lines.extend(
            [
                "## 运行结果",
                "",
                (
                    "本次没有生成完整的新词新概念情报项。"
                    "原因可能是没有新增政策、没有达到阈值的"
                    "候选概念，或部分分析阶段失败。"
                ),
                "",
            ]
        )

    for index, item in enumerate(
        run.intelligence_items,
        start=1,
    ):
        recommended_id = (
            item.feedback_ranking
            .ranking
            .recommended_answer_id
        )
        recommended = next(
            candidate
            for candidate
            in item.answer_package.candidates
            if candidate.answer_id
            == recommended_id
        )

        lines.extend(
            [
                (
                    f"## {index}. "
                    f"{item.candidate.term}"
                ),
                "",
                f"- 政策：{item.policy_title}",
                (
                    "- 发布机构："
                    f"{item.policy_source_name}"
                ),
                (
                    "- 权威来源："
                    f"{item.policy_source_url}"
                ),
                (
                    "- 候选类型："
                    f"{item.candidate.candidate_type.value}"
                ),
                (
                    "- 新颖度："
                    f"{item.candidate.novelty_score:.2f}"
                ),
                (
                    "- 发现置信度："
                    f"{item.candidate.confidence:.2f}"
                ),
                (
                    "- 时效性得分："
                    f"{item.timeliness_score:.2f}"
                ),
                "",
                "### 概念解释",
                "",
                item.analysis.explanation_draft,
                "",
                "### 广东电网总体影响",
                "",
                (
                    item.impact_assessment
                    .overall_summary
                ),
                "",
                "### 当前推荐回答",
                "",
                f"#### {recommended.title}",
                "",
                recommended.content,
                "",
                "### 推荐行动",
                "",
            ]
        )

        if recommended.action_items:
            lines.extend(
                f"- {action}"
                for action
                in recommended.action_items
            )
        else:
            lines.append("- 暂无")

        lines.append("")

    if run.failures:
        lines.extend(
            [
                "## 分析异常",
                "",
            ]
        )

        for failure in run.failures:
            term_text = (
                f" / {failure.term}"
                if failure.term
                else ""
            )
            lines.append(
                f"- {failure.policy_title}"
                f"{term_text} / {failure.stage}："
                f"{failure.error_type}："
                f"{failure.message}"
            )

        lines.append("")

    return "\n".join(lines)


def build_intelligence_brief_payload(
    *,
    task: TrackingTask,
    run: PolicyIntelligenceRun,
) -> dict[str, Any]:
    """生成可供平台投递的结构化智能简报。"""
    return {
        "schema_version": "1.0",
        "task": {
            "task_id": task.task_id,
            "name": task.name,
            "question": task.question,
            "keywords": task.keywords,
        },
        "summary": {
            "document_count": run.document_count,
            "analyzed_document_count": (
                run.analyzed_document_count
            ),
            "intelligence_item_count": len(
                run.intelligence_items
            ),
            "failure_count": len(
                run.failures
            ),
            "llm_stage_count": (
                run.llm_stage_count
            ),
        },
        "intelligence_items": [
            item.model_dump(
                mode="json",
                exclude={
                    "integrated_report_markdown",
                },
                exclude_none=True,
            )
            for item in run.intelligence_items
        ],
        "failures": [
            failure.model_dump(
                mode="json",
                exclude_none=True,
            )
            for failure in run.failures
        ],
        "report_markdown": (
            build_intelligence_brief_markdown(
                task=task,
                run=run,
            )
        ),
    }


def save_policy_intelligence_run(
    *,
    task: TrackingTask,
    run: PolicyIntelligenceRun,
    output_dir: str | Path,
) -> Path:
    """保存完整智能分析对象、单概念报告和运行级简报。"""
    directory = Path(output_dir)
    intelligence_directory = (
        directory / "intelligence"
    )
    intelligence_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    for item in run.intelligence_items:
        item_directory = (
            intelligence_directory
            / item.intelligence_id
        )
        item_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        model_files = {
            "concept_candidate.json": (
                item.candidate
            ),
            "concept_analysis.json": (
                item.analysis
            ),
            "business_impact.json": (
                item.impact_assessment
            ),
            "answer_package.json": (
                item.answer_package
            ),
            "feedback_ranking.json": (
                item.feedback_ranking
            ),
            "governance_tasks.json": (
                item.governance_batch
            ),
        }

        for filename, model in (
            model_files.items()
        ):
            (
                item_directory / filename
            ).write_text(
                model.model_dump_json(
                    indent=2,
                    exclude_none=True,
                ),
                encoding="utf-8",
            )

        (
            item_directory
            / "integrated_report.md"
        ).write_text(
            item.integrated_report_markdown,
            encoding="utf-8",
        )

    run_path = (
        directory / "intelligence_run.json"
    )
    run_path.write_text(
        run.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    markdown = (
        build_intelligence_brief_markdown(
            task=task,
            run=run,
        )
    )
    payload = build_intelligence_brief_payload(
        task=task,
        run=run,
    )
    (
        directory / "intelligence_brief.md"
    ).write_text(
        markdown,
        encoding="utf-8",
    )
    (
        directory / "intelligence_brief.json"
    ).write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_path
