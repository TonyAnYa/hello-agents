"""候选概念新颖度评分。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from enterprise_concept_radar.models import (
    ConceptBaseline,
    ConceptCandidateType,
)


class ConceptBaselineError(RuntimeError):
    """术语基线读取或校验失败。"""


@dataclass(frozen=True, slots=True)
class NoveltyAssessment:
    """一次新颖度比较的结果。"""

    score: float
    candidate_type: ConceptCandidateType
    first_seen_date: date | None
    related_terms: tuple[str, ...]
    explanation: str


def normalize_term(term: str) -> str:
    """标准化术语，减少空格和标点差异的影响。"""
    return re.sub(
        r"""[\s\-—_·（）()《》“”"'，,。！？；：:]""",
        "",
        term,
    ).casefold()


def load_concept_baseline(
    file_path: str | Path,
) -> ConceptBaseline:
    """从 JSON 文件读取术语基线。"""
    path = Path(file_path)

    if not path.is_file():
        raise ConceptBaselineError(
            f"术语基线文件不存在：{path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ConceptBaselineError(
            f"术语基线 JSON 格式错误：{path.name}；{exc}"
        ) from exc
    except OSError as exc:
        raise ConceptBaselineError(
            f"无法读取术语基线：{path}；{exc}"
        ) from exc

    try:
        return ConceptBaseline.model_validate(raw_data)
    except ValidationError as exc:
        raise ConceptBaselineError(
            f"术语基线字段校验失败：{path.name}\n{exc}"
        ) from exc


def assess_term_novelty(
    term: str,
    baseline: ConceptBaseline,
) -> NoveltyAssessment:
    """将候选术语与历史基线进行比较。

    当前 MVP 使用三档透明规则：

    1. 与历史术语或别名完全相同：
       视为已有概念再次出现，新颖度为 25。
    2. 与历史术语存在包含关系：
       视为在已有概念上的新增说法，新颖度为 82。
    3. 未发现明显关联：
       暂视为新增概念，新颖度为 92。

    这些分数是候选筛选分，不等于最终政策结论。
    """
    normalized_term = normalize_term(term)

    exact_matches = []
    related_matches = []

    for known_term in baseline.known_terms:
        names = [
            known_term.term,
            *known_term.aliases,
        ]

        normalized_names = {
            normalize_term(name)
            for name in names
        }

        if normalized_term in normalized_names:
            exact_matches.append(known_term)
            continue

        has_containment_relation = any(
            normalized_name in normalized_term
            or normalized_term in normalized_name
            for normalized_name in normalized_names
        )

        if has_containment_relation:
            related_matches.append(known_term)

    if exact_matches:
        matched = exact_matches[0]

        return NoveltyAssessment(
            score=25,
            candidate_type=ConceptCandidateType.HEATING_CONCEPT,
            first_seen_date=matched.first_seen_date,
            related_terms=(matched.term,),
            explanation=(
                f"该表述与历史基线术语“{matched.term}”完全匹配，"
                "暂按已有概念再次出现处理。"
            ),
        )

    if related_matches:
        related_names = tuple(
            item.term
            for item in related_matches
        )

        known_dates = [
            item.first_seen_date
            for item in related_matches
            if item.first_seen_date is not None
        ]

        first_seen_date = (
            min(known_dates)
            if known_dates
            else None
        )

        return NoveltyAssessment(
            score=82,
            candidate_type=ConceptCandidateType.NEW_EXPRESSION,
            first_seen_date=first_seen_date,
            related_terms=related_names,
            explanation=(
                "该表述未与历史术语完全匹配，但与既有概念"
                f"“{'、'.join(related_names)}”存在包含关系，"
                "暂按新增说法或概念扩展处理。"
            ),
        )

    return NoveltyAssessment(
        score=92,
        candidate_type=ConceptCandidateType.NEW_CONCEPT,
        first_seen_date=None,
        related_terms=(),
        explanation=(
            "未在当前教学基线中发现完全匹配或明显包含关系，"
            "暂按新增概念候选处理，仍需权威原文和历史语料复核。"
        ),
    )
