"""多来源真实政策搜索、正文抓取、LLM 识别与去重编排。"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.agents.policy_document_extractor_agent import (
    PolicyDocumentRejected,
    build_policy_document_extractor_agent,
    extract_policy_document,
)
from enterprise_concept_radar.models import PolicyDocument
from enterprise_concept_radar.policy_sources import (
    PolicySourceSelection,
)
from enterprise_concept_radar.services.policy_search import (
    PolicySearchResult,
    search_policy_candidates,
)
from enterprise_concept_radar.services.web_fetcher import (
    FetchedWebPage,
    fetch_web_page,
)
from enterprise_concept_radar.tracking_tasks import (
    DateRangeMode,
    TrackingTask,
    TrackingTaskState,
)


class PolicyCollectionError(RuntimeError):
    """在线政策批量采集无法继续执行。"""


class CollectionFailure(BaseModel):
    """采集过程中一个可审计的失败记录。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    stage: str = Field(
        min_length=1,
        description="失败阶段",
    )
    source_id: str = Field(
        min_length=1,
        description="政策源 ID",
    )
    url: str | None = Field(
        default=None,
        description="失败网页地址",
    )
    error_type: str = Field(
        min_length=1,
        description="异常类型",
    )
    message: str = Field(
        min_length=1,
        description="错误摘要",
    )


class SourceCollectionStatus(BaseModel):
    """一个政策源的采集统计。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    source_slot: int = Field(
        ge=1,
        le=6,
    )
    source_id: str = Field(
        min_length=1,
    )
    source_name: str = Field(
        min_length=1,
    )
    search_succeeded: bool
    candidate_count: int = Field(
        ge=0,
    )
    fetched_count: int = Field(
        ge=0,
    )
    accepted_policy_count: int = Field(
        ge=0,
    )


class PolicyCollectionRun(BaseModel):
    """一次多来源在线政策采集结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task_id: str = Field(
        min_length=1,
    )
    run_id: str = Field(
        min_length=1,
    )
    started_at: datetime
    completed_at: datetime
    published_after: date
    published_before: date
    documents: list[PolicyDocument] = Field(
        default_factory=list,
    )
    document_fingerprints: list[str] = Field(
        default_factory=list,
    )
    source_statuses: list[
        SourceCollectionStatus
    ] = Field(
        default_factory=list,
    )
    failures: list[CollectionFailure] = Field(
        default_factory=list,
    )
    searched_candidate_count: int = Field(
        ge=0,
    )
    fetched_page_count: int = Field(
        ge=0,
    )
    llm_call_count: int = Field(
        ge=0,
    )
    duplicate_count: int = Field(
        ge=0,
    )
    previously_delivered_count: int = Field(
        ge=0,
    )


def normalize_identity_text(value: str) -> str:
    """标准化政策身份文本，供稳定去重使用。"""
    return re.sub(
        r"[\W_]+",
        "",
        value.casefold(),
        flags=re.UNICODE,
    )


def build_policy_fingerprint(
    document: PolicyDocument,
) -> str:
    """根据政策身份、文号、日期和正文哈希生成指纹。"""
    metadata = document.metadata
    document_number = str(
        metadata.get("document_number") or ""
    )
    content_hash = str(
        metadata.get("content_sha256") or ""
    )

    identity = "|".join(
        [
            normalize_identity_text(document.title),
            normalize_identity_text(
                document.source_name
            ),
            normalize_identity_text(
                document_number
            ),
            document.published_date.isoformat(),
            content_hash,
        ]
    )

    return hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()


def calculate_search_window(
    *,
    task: TrackingTask,
    state: TrackingTaskState,
    now: datetime,
) -> tuple[date, date]:
    """根据任务规则计算本次搜索日期范围。"""
    timezone_info = ZoneInfo(
        task.schedule.timezone
    )
    local_now = now.astimezone(timezone_info)

    if (
        task.date_range.mode
        == DateRangeMode.SINCE_LAST_SUCCESS
        and state.last_successful_at is not None
    ):
        start_time = (
            state.last_successful_at
            .astimezone(timezone_info)
            - timedelta(
                hours=task.date_range.overlap_hours
            )
        )
    else:
        lookback_days = (
            task.date_range.rolling_days
            if (
                task.date_range.mode
                == DateRangeMode.ROLLING_DAYS
            )
            else task.date_range.initial_lookback_days
        )
        start_time = local_now - timedelta(
            days=lookback_days
        )

    return (
        start_time.date(),
        local_now.date(),
    )


def candidate_is_excluded(
    candidate: PolicySearchResult,
    exclude_keywords: list[str],
) -> bool:
    """在下载前过滤明显无关的搜索结果。"""
    searchable_text = (
        f"{candidate.title}\n{candidate.snippet}"
    ).casefold()

    return any(
        keyword.casefold() in searchable_text
        for keyword in exclude_keywords
        if keyword.strip()
    )


def _save_page_snapshot(
    *,
    page: FetchedWebPage,
    artifact_dir: Path,
) -> str:
    """保存每个真实网页的原始 HTML 与清洗文本。"""
    digest = hashlib.sha256(
        page.final_url.encode("utf-8")
    ).hexdigest()[:20]
    raw_dir = artifact_dir / "raw_pages"
    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_path = raw_dir / f"{digest}.html"
    text_path = raw_dir / f"{digest}.txt"
    html_path.write_text(
        page.html,
        encoding="utf-8",
    )
    text_path.write_text(
        page.text,
        encoding="utf-8",
    )

    return str(
        html_path.relative_to(artifact_dir)
    )


def _merge_discovery_record(
    existing: PolicyDocument,
    duplicate: PolicyDocument,
) -> PolicyDocument:
    """同一政策被多个来源发现时保留全部发现记录。"""
    metadata = dict(existing.metadata)
    records = list(
        metadata.get("discovered_sources") or []
    )

    current_record = {
        "source_id": duplicate.metadata.get(
            "source_id"
        ),
        "source_slot": duplicate.metadata.get(
            "source_slot"
        ),
        "requested_url": duplicate.metadata.get(
            "requested_url"
        ),
        "final_url": duplicate.metadata.get(
            "final_url"
        ),
        "search_query": duplicate.metadata.get(
            "search_query"
        ),
    }

    if current_record not in records:
        records.append(current_record)

    metadata["discovered_sources"] = records

    return existing.model_copy(
        update={
            "metadata": metadata,
        }
    )


def collect_online_policies(
    *,
    task: TrackingTask,
    source_selection: PolicySourceSelection,
    state: TrackingTaskState,
    now: datetime | None = None,
    artifact_dir: str | Path | None = None,
    search_func: Callable[..., list[PolicySearchResult]] = (
        search_policy_candidates
    ),
    fetch_func: Callable[..., FetchedWebPage] = (
        fetch_web_page
    ),
    extract_func: Callable[..., PolicyDocument | None] = (
        extract_policy_document
    ),
    extractor_agent: Any | None = None,
) -> PolicyCollectionRun:
    """执行一次真实多来源政策采集。

    搜索或抓取单个来源失败时继续处理其他来源；
    所有启用来源搜索都失败时才终止整个任务。
    """
    active_now = now or datetime.now(timezone.utc)
    started_at = active_now.astimezone(
        timezone.utc
    )
    run_id = started_at.strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    published_after, published_before = (
        calculate_search_window(
            task=task,
            state=state,
            now=active_now,
        )
    )
    active_artifact_dir = (
        Path(artifact_dir)
        if artifact_dir is not None
        else None
    )

    if active_artifact_dir is not None:
        active_artifact_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    active_agent = extractor_agent

    if (
        active_agent is None
        and extract_func is extract_policy_document
    ):
        active_agent = (
            build_policy_document_extractor_agent()
        )

    source_statuses: list[
        SourceCollectionStatus
    ] = []
    failures: list[CollectionFailure] = []
    documents_by_fingerprint: dict[
        str,
        PolicyDocument,
    ] = {}
    searched_candidate_count = 0
    fetched_page_count = 0
    llm_call_count = 0
    duplicate_count = 0
    previously_delivered_count = 0
    successful_searches = 0
    processed_urls: set[str] = set()
    delivered = set(
        state.delivered_fingerprints
    )

    stop_processing = False

    for source in source_selection.selected_sources():
        source_name = (
            source.name
            or "不指定来源（全网搜索）"
        )
        fetched_for_source = 0
        accepted_for_source = 0

        try:
            candidates = search_func(
                source=source,
                question=task.question,
                keywords=task.keywords,
                published_after=published_after,
                published_before=published_before,
                max_results=(
                    task.max_results_per_source
                ),
            )
            successful_searches += 1
        except Exception as exc:
            failures.append(
                CollectionFailure(
                    stage="search",
                    source_id=source.source_id,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            source_statuses.append(
                SourceCollectionStatus(
                    source_slot=source.slot,
                    source_id=source.source_id,
                    source_name=source_name,
                    search_succeeded=False,
                    candidate_count=0,
                    fetched_count=0,
                    accepted_policy_count=0,
                )
            )
            continue

        searched_candidate_count += len(candidates)

        for candidate in candidates:
            if (
                len(processed_urls)
                >= task.max_candidates_per_run
            ):
                stop_processing = True
                break

            if candidate.url in processed_urls:
                duplicate_count += 1
                continue

            processed_urls.add(candidate.url)

            if candidate_is_excluded(
                candidate,
                task.exclude_keywords,
            ):
                continue

            try:
                page = fetch_func(candidate.url)
                fetched_page_count += 1
                fetched_for_source += 1

                snapshot_path = None

                if active_artifact_dir is not None:
                    snapshot_path = (
                        _save_page_snapshot(
                            page=page,
                            artifact_dir=(
                                active_artifact_dir
                            ),
                        )
                    )

                llm_call_count += 1
                extraction_kwargs: dict[
                    str,
                    Any,
                ] = {
                    "page": page,
                    "source_name_hint": (
                        source_name
                    ),
                    "source_slot": source.slot,
                    "source_id": source.source_id,
                    "user_question": task.question,
                    "keywords": task.keywords,
                    "search_query": candidate.query,
                    "search_snippet": (
                        candidate.snippet
                    ),
                    "agent": active_agent,
                }

                if (
                    extract_func
                    is extract_policy_document
                ):
                    extraction_kwargs[
                        "raise_on_rejection"
                    ] = True

                document = extract_func(
                    **extraction_kwargs
                )
            except PolicyDocumentRejected as exc:
                failures.append(
                    CollectionFailure(
                        stage="policy_rejected",
                        source_id=source.source_id,
                        url=candidate.url,
                        error_type=(
                            type(exc).__name__
                        ),
                        message=(
                            f"{exc}；"
                            f"识别置信度："
                            f"{exc.confidence:.2f}；"
                            f"网页编码："
                            f"{page.encoding}；"
                            f"正文长度："
                            f"{len(page.text)}"
                        ),
                    )
                )
                continue
            except Exception as exc:
                failures.append(
                    CollectionFailure(
                        stage="fetch_or_extract",
                        source_id=source.source_id,
                        url=candidate.url,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue

            if document is None:
                continue

            if snapshot_path is not None:
                metadata = dict(document.metadata)
                metadata["snapshot_path"] = (
                    snapshot_path
                )
                document = document.model_copy(
                    update={
                        "metadata": metadata,
                    }
                )

            fingerprint = build_policy_fingerprint(
                document
            )

            if (
                task.only_new_policies
                and fingerprint in delivered
            ):
                previously_delivered_count += 1
                continue

            existing = documents_by_fingerprint.get(
                fingerprint
            )

            if existing is not None:
                duplicate_count += 1
                documents_by_fingerprint[
                    fingerprint
                ] = _merge_discovery_record(
                    existing,
                    document,
                )
                continue

            documents_by_fingerprint[
                fingerprint
            ] = document
            accepted_for_source += 1

            if (
                len(documents_by_fingerprint)
                >= task.max_policies_per_run
            ):
                stop_processing = True
                break

        source_statuses.append(
            SourceCollectionStatus(
                source_slot=source.slot,
                source_id=source.source_id,
                source_name=source_name,
                search_succeeded=True,
                candidate_count=len(candidates),
                fetched_count=fetched_for_source,
                accepted_policy_count=(
                    accepted_for_source
                ),
            )
        )

        if stop_processing:
            break

    if successful_searches == 0:
        error_text = "；".join(
            failure.message
            for failure in failures
        )
        raise PolicyCollectionError(
            "所有已启用政策源搜索均失败"
            + (
                f"：{error_text}"
                if error_text
                else ""
            )
        )

    completed_at = datetime.now(
        timezone.utc
    )
    fingerprints = list(
        documents_by_fingerprint
    )

    return PolicyCollectionRun(
        task_id=task.task_id,
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        published_after=published_after,
        published_before=published_before,
        documents=list(
            documents_by_fingerprint.values()
        ),
        document_fingerprints=fingerprints,
        source_statuses=source_statuses,
        failures=failures,
        searched_candidate_count=(
            searched_candidate_count
        ),
        fetched_page_count=fetched_page_count,
        llm_call_count=llm_call_count,
        duplicate_count=duplicate_count,
        previously_delivered_count=(
            previously_delivered_count
        ),
    )


def save_collection_run(
    run: PolicyCollectionRun,
    output_dir: str | Path,
) -> Path:
    """保存采集运行清单和每份标准政策 JSON。"""
    directory = Path(output_dir)
    documents_dir = directory / "documents"
    documents_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for document in run.documents:
        document_path = (
            documents_dir
            / f"{document.document_id}.json"
        )
        document_path.write_text(
            document.model_dump_json(
                indent=2,
                exclude_none=True,
            ),
            encoding="utf-8",
        )

    run_path = directory / "collection_run.json"
    run_path.write_text(
        run.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    return run_path
