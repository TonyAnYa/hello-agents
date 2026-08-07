"""持久化真实运行中已经观察到的概念历史。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    BaselineTerm,
    ConceptBaseline,
)
from enterprise_concept_radar.scoring.novelty import (
    load_concept_baseline,
    normalize_term,
)


class ConceptHistoryOccurrence(BaseModel):
    """一个概念在一份真实政策中的观察记录。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    document_id: str = Field(min_length=1)
    term: str = Field(min_length=1)
    policy_title: str = Field(min_length=1)
    policy_source_name: str = Field(min_length=1)
    policy_source_url: str = Field(min_length=1)
    published_date: date
    observed_at: datetime


class ConceptHistoryEntry(BaseModel):
    """一个规范化概念的本地历史。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    normalized_term: str = Field(min_length=1)
    canonical_term: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    first_seen_date: date
    last_seen_date: date
    occurrences: list[ConceptHistoryOccurrence] = Field(
        default_factory=list,
    )


class ConceptHistoryStore(BaseModel):
    """一个追踪任务的概念历史库。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task_id: str = Field(min_length=1)
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
    entries: list[ConceptHistoryEntry] = Field(
        default_factory=list,
    )


def concept_history_path(task_id: str) -> Path:
    """返回任务对应的运行时概念历史路径。"""
    return (
        RUNTIME_DATA_DIR
        / "tracking"
        / "concept_history"
        / f"{task_id}.json"
    )


def load_concept_history(
    *,
    task_id: str,
    path: str | Path | None = None,
) -> ConceptHistoryStore:
    """读取概念历史；不存在时返回空历史。"""
    active_path = (
        Path(path)
        if path is not None
        else concept_history_path(task_id)
    )

    if not active_path.is_file():
        return ConceptHistoryStore(task_id=task_id)

    store = ConceptHistoryStore.model_validate_json(
        active_path.read_text(encoding="utf-8")
    )

    if store.task_id != task_id:
        raise ValueError(
            "概念历史 task_id 与当前任务不一致"
        )

    return store


def save_concept_history(
    store: ConceptHistoryStore,
    path: str | Path | None = None,
) -> Path:
    """原子化保存概念历史。"""
    active_path = (
        Path(path)
        if path is not None
        else concept_history_path(store.task_id)
    )
    active_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    temporary_path = active_path.with_suffix(
        ".json.tmp"
    )
    temporary_path.write_text(
        store.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(active_path)
    return active_path


def _unique_aliases(values: list[str]) -> list[str]:
    """按规范化形式去重别名。"""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()
        identity = normalize_term(cleaned)

        if not cleaned or not identity or identity in seen:
            continue

        result.append(cleaned)
        seen.add(identity)

    return result


def record_intelligence_history(
    *,
    task_id: str,
    collection_run: Any,
    intelligence_run: Any,
    path: str | Path | None = None,
) -> ConceptHistoryStore:
    """把一次成功真实运行中的完整概念情报写入历史。"""
    store = load_concept_history(
        task_id=task_id,
        path=path,
    )
    documents = {
        document.document_id: document
        for document in collection_run.documents
    }
    entries_by_term = {
        entry.normalized_term: entry
        for entry in store.entries
    }

    for item in intelligence_run.intelligence_items:
        document = documents.get(item.document_id)

        if document is None:
            continue

        term = item.candidate.term.strip()
        normalized = normalize_term(term)

        if not normalized:
            continue

        occurrence = ConceptHistoryOccurrence(
            document_id=item.document_id,
            term=term,
            policy_title=item.policy_title,
            policy_source_name=item.policy_source_name,
            policy_source_url=item.policy_source_url,
            published_date=document.published_date,
            observed_at=item.candidate.detected_at,
        )
        existing = entries_by_term.get(normalized)

        if existing is None:
            entries_by_term[normalized] = ConceptHistoryEntry(
                normalized_term=normalized,
                canonical_term=term,
                aliases=[],
                first_seen_date=document.published_date,
                last_seen_date=document.published_date,
                occurrences=[occurrence],
            )
            continue

        aliases = _unique_aliases(
            [*existing.aliases, term]
        )
        aliases = [
            alias
            for alias in aliases
            if normalize_term(alias)
            != normalize_term(existing.canonical_term)
        ]
        occurrence_keys = {
            (old.document_id, normalize_term(old.term))
            for old in existing.occurrences
        }
        occurrences = list(existing.occurrences)

        if (item.document_id, normalized) not in occurrence_keys:
            occurrences.append(occurrence)

        entries_by_term[normalized] = existing.model_copy(
            update={
                "aliases": aliases,
                "first_seen_date": min(
                    existing.first_seen_date,
                    document.published_date,
                ),
                "last_seen_date": max(
                    existing.last_seen_date,
                    document.published_date,
                ),
                "occurrences": occurrences[-100:],
            }
        )

    updated = store.model_copy(
        update={
            "updated_at": datetime.now(timezone.utc),
            "entries": sorted(
                entries_by_term.values(),
                key=lambda entry: (
                    entry.first_seen_date,
                    entry.canonical_term,
                ),
            ),
        }
    )
    save_concept_history(updated, path=path)
    return updated


def merge_baseline_with_history(
    *,
    baseline: ConceptBaseline,
    history: ConceptHistoryStore,
) -> ConceptBaseline:
    """将运行历史合并进静态种子基线。"""
    known_terms = list(baseline.known_terms)
    normalized_known: set[str] = set()

    for item in known_terms:
        normalized_known.add(normalize_term(item.term))
        normalized_known.update(
            normalize_term(alias)
            for alias in item.aliases
        )

    for entry in history.entries:
        if entry.normalized_term in normalized_known:
            continue

        aliases = _unique_aliases(entry.aliases)
        known_terms.append(
            BaselineTerm(
                term=entry.canonical_term,
                first_seen_date=entry.first_seen_date,
                aliases=aliases,
                source=(
                    "EnterpriseConceptRadar 真实运行历史"
                ),
            )
        )
        normalized_known.add(entry.normalized_term)
        normalized_known.update(
            normalize_term(alias)
            for alias in aliases
        )

    return baseline.model_copy(
        update={
            "version": (
                f"{baseline.version}+runtime-history"
            ),
            "known_terms": known_terms,
        }
    )


def build_effective_concept_baseline(
    task_id: str,
) -> ConceptBaseline:
    """构建静态基线 + 当前任务真实运行历史。"""
    baseline = load_concept_baseline(
        BASELINE_DATA_DIR / "known_terms.json"
    )
    history = load_concept_history(task_id=task_id)
    return merge_baseline_with_history(
        baseline=baseline,
        history=history,
    )
