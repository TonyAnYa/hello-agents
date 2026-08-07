"""使用大模型从真实政策正文中发现新词和新概念候选。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from enterprise_concept_radar.agents.concept_analysis_agent import (
    StructuredSimpleAgent,
    extract_json_object,
)
from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.models import (
    ConceptBaseline,
    ConceptCandidate,
    PolicyDocument,
)
from enterprise_concept_radar.scoring.novelty import (
    assess_term_novelty,
    normalize_term,
)
from enterprise_concept_radar.services.llm import (
    LLMSettings,
    build_llm,
)

MAX_DISCOVERY_TEXT_LENGTH = 36_000


class ConceptDiscoveryError(RuntimeError):
    """概念发现模型调用或结果校验失败。"""


class ConceptDiscoveryRunner(Protocol):
    """ConceptDiscoveryAgent 所需的最小运行接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回字符串。"""


class ConceptProposal(BaseModel):
    """LLM 从政策原文中提出的一个概念候选。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    term: str = Field(
        min_length=2,
        max_length=40,
        description="政策中的新词、新说法或新概念",
    )
    evidence_quote: str = Field(
        min_length=2,
        max_length=500,
        description="包含该术语的政策原文",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="候选识别置信度",
    )
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="候选理由",
    )


class ConceptDiscoveryResponse(BaseModel):
    """ConceptDiscoveryAgent 的结构化响应。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    candidates: list[ConceptProposal] = Field(
        default_factory=list,
        max_length=20,
        description="概念候选列表",
    )


def load_concept_discovery_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取概念发现系统提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else (
            CONFIG_DIR
            / "prompts"
            / "concept_discovery.md"
        )
    )

    if not path.is_file():
        raise ConceptDiscoveryError(
            f"概念发现提示词不存在：{path}"
        )

    try:
        content = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as exc:
        raise ConceptDiscoveryError(
            f"无法读取概念发现提示词：{path}；{exc}"
        ) from exc

    if not content:
        raise ConceptDiscoveryError(
            f"概念发现提示词为空：{path}"
        )

    return content


def build_concept_discovery_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建在线政策概念发现 Agent。"""
    active_settings = (
        settings or LLMSettings.from_env()
    )

    return StructuredSimpleAgent(
        name="ConceptDiscoveryAgent",
        llm=build_llm(active_settings),
        system_prompt=(
            load_concept_discovery_prompt()
        ),
        enable_tool_calling=False,
    )


def build_concept_discovery_input(
    *,
    document: PolicyDocument,
    baseline: ConceptBaseline,
    question: str,
    focus_keywords: list[str],
    maximum_candidates: int,
) -> str:
    """构建发送给模型的真实政策材料。"""
    payload = {
        "task": (
            "从真实政策正文中发现值得持续追踪的"
            "新词、新说法和新概念"
        ),
        "user_question": question,
        "focus_keywords": focus_keywords,
        "maximum_candidates": maximum_candidates,
        "known_baseline_terms": [
            {
                "term": item.term,
                "aliases": item.aliases,
                "first_seen_date": (
                    item.first_seen_date.isoformat()
                    if item.first_seen_date
                    else None
                ),
            }
            for item in baseline.known_terms
        ],
        "policy_document": {
            "document_id": document.document_id,
            "title": document.title,
            "source_name": document.source_name,
            "source_url": str(document.source_url),
            "published_date": (
                document.published_date.isoformat()
            ),
            "document_type": (
                document.document_type.value
            ),
            "is_simulated": document.is_simulated,
            "content": document.content[
                :MAX_DISCOVERY_TEXT_LENGTH
            ],
        },
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def parse_concept_discovery_response(
    *,
    raw_response: str,
    document: PolicyDocument,
    baseline: ConceptBaseline,
    maximum_candidates: int,
    minimum_confidence: float,
    minimum_term_length: int = 2,
    ignored_terms: set[str] | frozenset[str] = frozenset(),
) -> list[ConceptCandidate]:
    """解析 LLM 结果并使用本地证据与基线重新校验。"""
    try:
        response = ConceptDiscoveryResponse.model_validate(
            extract_json_object(raw_response)
        )
    except ValidationError as exc:
        raise ConceptDiscoveryError(
            f"概念发现结果字段无效：\n{exc}"
        ) from exc

    candidates: list[ConceptCandidate] = []
    seen_terms: set[str] = set()
    normalized_ignored = {
        normalize_term(term)
        for term in ignored_terms
    }

    for proposal in response.candidates:
        term = proposal.term.strip()
        normalized = normalize_term(term)

        if len(term) < minimum_term_length:
            continue

        if not normalized:
            continue

        if normalized in normalized_ignored:
            continue

        if normalized in seen_terms:
            continue

        if proposal.confidence < minimum_confidence:
            continue

        # 两项证据校验都必须通过：
        # 1. 证据句必须真实存在于抓取正文；
        # 2. 证据句必须包含候选术语。
        if (
            proposal.evidence_quote
            not in document.content
        ):
            continue

        if term not in proposal.evidence_quote:
            continue

        novelty = assess_term_novelty(
            term,
            baseline,
        )
        candidates.append(
            ConceptCandidate(
                term=term,
                source_document_id=(
                    document.document_id
                ),
                evidence_quote=(
                    proposal.evidence_quote
                ),
                candidate_type=(
                    novelty.candidate_type
                ),
                novelty_score=novelty.score,
                confidence=proposal.confidence,
                first_seen_date=(
                    novelty.first_seen_date
                ),
                related_terms=list(
                    novelty.related_terms
                ),
                explanation=(
                    f"{novelty.explanation}"
                    f"模型候选理由：{proposal.reason}"
                ),
            )
        )
        seen_terms.add(normalized)

    ordered = sorted(
        candidates,
        key=lambda item: (
            item.novelty_score,
            item.confidence,
            item.term,
        ),
        reverse=True,
    )

    return ordered[:maximum_candidates]


def discover_policy_concepts(
    *,
    document: PolicyDocument,
    baseline: ConceptBaseline,
    question: str,
    focus_keywords: list[str],
    maximum_candidates: int = 3,
    minimum_confidence: float = 0.65,
    minimum_term_length: int = 2,
    ignored_terms: set[str] | frozenset[str] = frozenset(),
    agent: ConceptDiscoveryRunner | None = None,
    settings: LLMSettings | None = None,
) -> list[ConceptCandidate]:
    """调用 ConceptDiscoveryAgent 发现并校验候选概念。"""
    if document.is_simulated:
        raise ConceptDiscoveryError(
            "在线概念发现不能使用模拟政策"
        )

    if maximum_candidates <= 0:
        raise ConceptDiscoveryError(
            "maximum_candidates 必须大于 0"
        )

    active_agent = (
        agent
        if agent is not None
        else build_concept_discovery_agent(
            settings
        )
    )
    input_text = build_concept_discovery_input(
        document=document,
        baseline=baseline,
        question=question,
        focus_keywords=focus_keywords,
        maximum_candidates=maximum_candidates,
    )

    try:
        response = active_agent.run(
            input_text,
            max_tokens=1800,
        )
    except Exception as exc:
        raise ConceptDiscoveryError(
            "ConceptDiscoveryAgent 调用失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if (
        not isinstance(response, str)
        or not response.strip()
    ):
        raise ConceptDiscoveryError(
            "ConceptDiscoveryAgent 返回了空结果"
        )

    return parse_concept_discovery_response(
        raw_response=response,
        document=document,
        baseline=baseline,
        maximum_candidates=maximum_candidates,
        minimum_confidence=minimum_confidence,
        minimum_term_length=minimum_term_length,
        ignored_terms=ignored_terms,
    )
