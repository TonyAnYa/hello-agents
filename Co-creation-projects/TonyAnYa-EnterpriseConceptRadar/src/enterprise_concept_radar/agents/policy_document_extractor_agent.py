"""调用大模型识别真实政策并生成标准 PolicyDocument。"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from enterprise_concept_radar.agents.concept_analysis_agent import (
    StructuredSimpleAgent,
    extract_json_object,
)
from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.models import (
    PolicyDocument,
    PolicyDocumentType,
)
from enterprise_concept_radar.services.llm import (
    LLMSettings,
    build_llm,
)
from enterprise_concept_radar.services.web_fetcher import (
    FetchedWebPage,
)

MAX_AGENT_TEXT_LENGTH = 32_000


class PolicyDocumentExtractionError(RuntimeError):
    """政策识别、模型调用或结构化结果校验失败。"""


class PolicyDocumentRejected(RuntimeError):
    """网页完成识别，但未通过正式政策准入。"""

    def __init__(
        self,
        *,
        reason: str,
        confidence: float,
        is_policy: bool,
    ) -> None:
        super().__init__(reason)
        self.confidence = confidence
        self.is_policy = is_policy


class PolicyDocumentExtractorRunner(Protocol):
    """政策文档提取 Agent 所需的最小接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回字符串。"""


class PolicyDocumentDecision(BaseModel):
    """LLM 对一个真实网页作出的政策识别结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    is_policy: bool = Field(
        description="网页是否包含正式政策正文",
    )
    title: str | None = Field(
        default=None,
        description="政策正式标题",
    )
    issuing_authority: str | None = Field(
        default=None,
        description="政策发布机构",
    )
    published_date: date | None = Field(
        default=None,
        description="政策发布日期",
    )
    document_type: PolicyDocumentType = Field(
        default=PolicyDocumentType.OTHER,
        description="政策文件类型",
    )
    document_number: str | None = Field(
        default=None,
        description="政策文号",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="政策识别置信度",
    )
    evidence_quotes: list[str] = Field(
        default_factory=list,
        description="支持判断的网页原文证据",
    )
    rejection_reason: str | None = Field(
        default=None,
        description="判定为非政策时的原因",
    )

    @model_validator(mode="after")
    def policy_fields_are_required(
        self,
    ) -> "PolicyDocumentDecision":
        """正式政策必须具备最基本的身份字段。"""
        if self.is_policy:
            missing: list[str] = []

            if self.title is None:
                missing.append("title")
            if self.issuing_authority is None:
                missing.append("issuing_authority")
            if self.published_date is None:
                missing.append("published_date")

            if missing:
                raise ValueError(
                    "正式政策缺少必要字段："
                    + "、".join(missing)
                )

        return self


def load_policy_document_extractor_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取真实政策识别提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else (
            CONFIG_DIR
            / "prompts"
            / "policy_document_extractor.md"
        )
    )

    if not path.is_file():
        raise PolicyDocumentExtractionError(
            f"政策识别提示词不存在：{path}"
        )

    try:
        content = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as exc:
        raise PolicyDocumentExtractionError(
            f"无法读取政策识别提示词：{path}；{exc}"
        ) from exc

    if not content:
        raise PolicyDocumentExtractionError(
            f"政策识别提示词为空：{path}"
        )

    return content


def build_policy_document_extractor_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建真实政策识别智能体。"""
    active_settings = (
        settings
        or LLMSettings.from_env()
    )

    return StructuredSimpleAgent(
        name="PolicyDocumentExtractorAgent",
        llm=build_llm(active_settings),
        system_prompt=(
            load_policy_document_extractor_prompt()
        ),
        enable_tool_calling=False,
    )


def build_policy_document_extractor_input(
    *,
    page: FetchedWebPage,
    source_name_hint: str,
    user_question: str = "",
    keywords: list[str] | None = None,
) -> str:
    """构造发送给 LLM 的真实网页材料。"""
    payload = {
        "task": (
            "判断网页是否为正式政策，并提取政策身份字段"
        ),
        "source_name_hint": source_name_hint,
        "user_question": user_question,
        "keywords": keywords or [],
        "web_page": {
            "requested_url": page.requested_url,
            "final_url": page.final_url,
            "page_title": page.title,
            "content_type": page.content_type,
            "encoding": page.encoding,
            "text": page.text[
                :MAX_AGENT_TEXT_LENGTH
            ],
        },
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def parse_policy_document_decision(
    raw_response: str,
) -> PolicyDocumentDecision:
    """解析并校验 LLM 的政策识别结果。"""
    try:
        return PolicyDocumentDecision.model_validate(
            extract_json_object(raw_response)
        )
    except ValidationError as exc:
        raise PolicyDocumentExtractionError(
            f"政策识别结果字段无效：\n{exc}"
        ) from exc


def _build_document_id(
    decision: PolicyDocumentDecision,
    page: FetchedWebPage,
) -> str:
    """根据政策身份信息生成稳定文档 ID。"""
    identity = "|".join(
        [
            decision.title or "",
            decision.issuing_authority or "",
            (
                decision.published_date.isoformat()
                if decision.published_date
                else ""
            ),
            decision.document_number or "",
            page.final_url,
        ]
    )
    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:20]

    return f"online-{digest}"


def build_policy_document(
    *,
    page: FetchedWebPage,
    decision: PolicyDocumentDecision,
    source_slot: int,
    source_id: str,
    search_query: str | None = None,
    search_snippet: str | None = None,
    minimum_confidence: float = 0.60,
) -> PolicyDocument | None:
    """由已校验网页和 LLM 决策生成标准政策文档。

    URL 与正文始终取自本地真实抓取结果，不允许模型改写。
    """
    if not decision.is_policy:
        return None

    if decision.confidence < minimum_confidence:
        return None

    if (
        decision.title is None
        or decision.issuing_authority is None
        or decision.published_date is None
    ):
        raise PolicyDocumentExtractionError(
            "正式政策缺少必要身份字段"
        )

    content_hash = hashlib.sha256(
        page.text.encode("utf-8")
    ).hexdigest()

    return PolicyDocument(
        document_id=_build_document_id(
            decision,
            page,
        ),
        title=decision.title,
        source_name=decision.issuing_authority,
        source_url=page.final_url,
        published_date=decision.published_date,
        document_type=decision.document_type,
        content=page.text,
        fetched_at=page.fetched_at,
        is_simulated=False,
        metadata={
            "requested_url": page.requested_url,
            "final_url": page.final_url,
            "page_title": page.title,
            "http_status_code": page.status_code,
            "content_type": page.content_type,
            "detected_encoding": page.encoding,
            "content_sha256": content_hash,
            "document_number": decision.document_number,
            "source_slot": source_slot,
            "source_id": source_id,
            "search_query": search_query,
            "search_snippet": search_snippet,
            "llm_policy_confidence": decision.confidence,
            "llm_evidence_quotes": (
                decision.evidence_quotes
            ),
        },
    )


def extract_policy_document(
    *,
    page: FetchedWebPage,
    source_name_hint: str,
    source_slot: int,
    source_id: str,
    user_question: str = "",
    keywords: list[str] | None = None,
    search_query: str | None = None,
    search_snippet: str | None = None,
    agent: PolicyDocumentExtractorRunner | None = None,
    settings: LLMSettings | None = None,
    minimum_confidence: float = 0.60,
    raise_on_rejection: bool = False,
) -> PolicyDocument | None:
    """调用大模型识别网页，并返回真实 PolicyDocument。"""
    active_agent = (
        agent
        if agent is not None
        else build_policy_document_extractor_agent(
            settings
        )
    )

    input_text = (
        build_policy_document_extractor_input(
            page=page,
            source_name_hint=source_name_hint,
            user_question=user_question,
            keywords=keywords,
        )
    )

    try:
        response = active_agent.run(
            input_text,
            max_tokens=1400,
        )
    except Exception as exc:
        raise PolicyDocumentExtractionError(
            "PolicyDocumentExtractorAgent 调用失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(response, str):
        raise PolicyDocumentExtractionError(
            "PolicyDocumentExtractorAgent 返回值不是字符串"
        )

    if not response.strip():
        raise PolicyDocumentExtractionError(
            "PolicyDocumentExtractorAgent 返回了空结果"
        )

    decision = parse_policy_document_decision(
        response
    )

    if (
        raise_on_rejection
        and not decision.is_policy
    ):
        raise PolicyDocumentRejected(
            reason=(
                decision.rejection_reason
                or "模型判定网页不包含正式政策正文"
            ),
            confidence=decision.confidence,
            is_policy=False,
        )

    if (
        raise_on_rejection
        and decision.is_policy
        and decision.confidence
        < minimum_confidence
    ):
        raise PolicyDocumentRejected(
            reason=(
                "模型判断为政策，但识别置信度"
                f" {decision.confidence:.2f} "
                "低于准入阈值"
                f" {minimum_confidence:.2f}"
            ),
            confidence=decision.confidence,
            is_policy=True,
        )

    return build_policy_document(
        page=page,
        decision=decision,
        source_slot=source_slot,
        source_id=source_id,
        search_query=search_query,
        search_snippet=search_snippet,
        minimum_confidence=minimum_confidence,
    )
