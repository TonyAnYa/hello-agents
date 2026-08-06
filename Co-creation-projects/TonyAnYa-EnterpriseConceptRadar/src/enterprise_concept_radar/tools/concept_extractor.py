"""基于政策关键词和历史基线的候选概念提取工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from enterprise_concept_radar.models import (
    ConceptBaseline,
    ConceptCandidate,
    ConceptCandidateType,
    PolicyDocument,
)
from enterprise_concept_radar.scoring import (
    assess_term_novelty,
)


class ConceptRuleError(RuntimeError):
    """概念发现规则读取失败。"""


@dataclass(frozen=True, slots=True)
class ConceptRules:
    """概念提取规则。"""

    minimum_term_length: int
    maximum_candidates: int
    ignored_terms: frozenset[str]


def load_concept_rules(
    file_path: str | Path,
) -> ConceptRules:
    """从 YAML 文件读取概念发现规则。"""
    path = Path(file_path)

    if not path.is_file():
        raise ConceptRuleError(
            f"概念规则文件不存在：{path}"
        )

    try:
        with path.open("r", encoding="utf-8") as file:
            raw_data = yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        raise ConceptRuleError(
            f"概念规则 YAML 格式错误：{path.name}；{exc}"
        ) from exc
    except OSError as exc:
        raise ConceptRuleError(
            f"无法读取概念规则：{path}；{exc}"
        ) from exc

    minimum_term_length = int(
        raw_data.get("minimum_term_length", 2)
    )
    maximum_candidates = int(
        raw_data.get("maximum_candidates", 20)
    )
    ignored_terms = frozenset(
        str(term).strip()
        for term in raw_data.get("ignored_terms", [])
        if str(term).strip()
    )

    if minimum_term_length < 1:
        raise ConceptRuleError(
            "minimum_term_length 必须大于或等于 1"
        )

    if maximum_candidates < 1:
        raise ConceptRuleError(
            "maximum_candidates 必须大于或等于 1"
        )

    return ConceptRules(
        minimum_term_length=minimum_term_length,
        maximum_candidates=maximum_candidates,
        ignored_terms=ignored_terms,
    )


def split_policy_sentences(
    content: str,
) -> list[str]:
    """按照常见中文结束标点拆分政策正文。"""
    sentences = re.split(
        r"(?<=[。！？；])\s*",
        content,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def find_evidence_quote(
    content: str,
    term: str,
) -> str:
    """找到包含候选概念的第一条政策原句。"""
    for sentence in split_policy_sentences(content):
        if term in sentence:
            return sentence

    return content[:200].strip()


def build_candidate_explanation(
    assessment_explanation: str,
    evidence_quote: str,
) -> str:
    """组合规则判断和证据说明。"""
    return (
        f"{assessment_explanation}"
        f"当前证据句为：“{evidence_quote}”"
    )


def extract_concept_candidates(
    document: PolicyDocument,
    baseline: ConceptBaseline,
    rules: ConceptRules,
) -> list[ConceptCandidate]:
    """从政策关键词中提取候选概念。"""
    candidates: list[ConceptCandidate] = []
    seen_terms: set[str] = set()

    for keyword in document.keywords:
        term = keyword.strip()

        if not term:
            continue

        if term in seen_terms:
            continue

        if len(term) < rules.minimum_term_length:
            continue

        if term in rules.ignored_terms:
            continue

        evidence_quote = find_evidence_quote(
            document.content,
            term,
        )
        assessment = assess_term_novelty(
            term,
            baseline,
        )

        confidence = {
            ConceptCandidateType.HEATING_CONCEPT: 0.82,
            ConceptCandidateType.NEW_EXPRESSION: 0.88,
            ConceptCandidateType.NEW_CONCEPT: 0.75,
        }.get(
            assessment.candidate_type,
            0.70,
        )

        candidate = ConceptCandidate(
            term=term,
            source_document_id=document.document_id,
            evidence_quote=evidence_quote,
            candidate_type=assessment.candidate_type,
            novelty_score=assessment.score,
            confidence=confidence,
            first_seen_date=assessment.first_seen_date,
            related_terms=list(assessment.related_terms),
            explanation=build_candidate_explanation(
                assessment.explanation,
                evidence_quote,
            ),
        )

        candidates.append(candidate)
        seen_terms.add(term)

        if len(candidates) >= rules.maximum_candidates:
            break

    return candidates
