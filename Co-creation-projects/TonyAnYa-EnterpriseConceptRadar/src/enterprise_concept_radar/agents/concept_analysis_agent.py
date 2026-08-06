"""候选概念结构化分析智能体。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from hello_agents import SimpleAgent
from pydantic import ValidationError

from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.models import (
    ConceptAnalysis,
    ConceptCandidate,
    PolicyDocument,
)
from enterprise_concept_radar.services import (
    LLMSettings,
    build_llm,
)


class ConceptAnalysisError(RuntimeError):
    """候选概念分析或结果解析失败。"""


class AgentRunner(Protocol):
    """ConceptAnalysisAgent 所需的最小运行接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回文本。"""

class StructuredSimpleAgent(SimpleAgent):
    """适用于结构化、无状态任务的 SimpleAgent。"""

    def run(
        self,
        input_text: str,
        max_tool_iterations: int = 3,
        **kwargs: object,
    ) -> str:
        """以 JSON 模式调用模型，并在空响应时重试一次。"""
        # 当前 Agent 不调用工具。
        # 保留该参数是为了兼容 SimpleAgent.run 的公开接口。
        del max_tool_iterations

        messages: list[dict[str, str]] = []

        if self.system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self.system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": input_text,
            }
        )

        request_kwargs = dict(kwargs)

        request_kwargs.setdefault(
            "response_format",
            {
                "type": "json_object",
            },
        )

        extra_body_value = request_kwargs.get("extra_body")

        if isinstance(extra_body_value, dict):
            extra_body = dict(extra_body_value)
        else:
            extra_body = {}

        extra_body.setdefault(
            "thinking",
            {
                "type": "disabled",
            },
        )
        request_kwargs["extra_body"] = extra_body

        for attempt in range(2):
            active_messages = list(messages)

            if attempt == 1:
                active_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "上一次没有返回最终内容。"
                            "请立即只输出一个完整、合法的 JSON 对象，"
                            "不要输出解释、Markdown 或代码围栏。"
                        ),
                    }
                )

            response = self.llm.invoke(
                active_messages,
                **request_kwargs,
            )

            if not isinstance(response, str):
                raise ConceptAnalysisError(
                    "HelloAgentsLLM 返回结果不是字符串"
                )

            cleaned_response = response.strip()

            if cleaned_response:
                return cleaned_response

        raise ConceptAnalysisError(
            "模型连续两次返回空结果"
        )

def load_concept_analysis_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取概念分析 Agent 的系统提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else CONFIG_DIR / "prompts" / "concept_analysis.md"
    )

    if not path.is_file():
        raise ConceptAnalysisError(
            f"概念分析提示词不存在：{path}"
        )

    try:
        content = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as exc:
        raise ConceptAnalysisError(
            f"无法读取概念分析提示词：{path}；{exc}"
        ) from exc

    if not content:
        raise ConceptAnalysisError(
            f"概念分析提示词为空：{path}"
        )

    return content


def build_concept_analysis_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建基于 HelloAgents 的概念分析智能体。"""
    active_settings = settings or LLMSettings.from_env()
    llm = build_llm(active_settings)

    return StructuredSimpleAgent(
        name="ConceptAnalysisAgent",
        llm=llm,
        system_prompt=load_concept_analysis_prompt(),
        enable_tool_calling=False,
    )

def build_analysis_input(
    document: PolicyDocument,
    candidate: ConceptCandidate,
) -> str:
    """构建发送给模型的结构化输入。"""
    payload = {
        "task": "分析候选政策概念并输出结构化 JSON",
        "policy_document": {
            "document_id": document.document_id,
            "title": document.title,
            "source_name": document.source_name,
            "source_url": str(document.source_url),
            "published_date": document.published_date.isoformat(),
            "document_type": document.document_type.value,
            "is_simulated": document.is_simulated,
            "content": document.content,
        },
        "candidate": {
            "term": candidate.term,
            "candidate_type": candidate.candidate_type.value,
            "novelty_score": candidate.novelty_score,
            "confidence": candidate.confidence,
            "evidence_quote": candidate.evidence_quote,
            "first_seen_date": (
                candidate.first_seen_date.isoformat()
                if candidate.first_seen_date
                else None
            ),
            "related_terms": candidate.related_terms,
            "rule_explanation": candidate.explanation,
        },
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def extract_json_object(
    raw_response: str,
) -> dict[str, object]:
    """从模型响应中提取第一个完整 JSON 对象。"""
    response = raw_response.strip()

    start = response.find("{")
    end = response.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ConceptAnalysisError(
            "模型响应中没有找到完整 JSON 对象"
        )

    json_text = response[start : end + 1]

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ConceptAnalysisError(
            f"模型返回的 JSON 无法解析：{exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ConceptAnalysisError(
            "模型返回的 JSON 顶层必须是对象"
        )

    return parsed


def parse_concept_analysis_response(
    raw_response: str,
    document: PolicyDocument,
    candidate: ConceptCandidate,
) -> ConceptAnalysis:
    """解析并校验模型生成的概念分析结果。"""
    raw_data = extract_json_object(raw_response)

    # 核心身份字段以本地已校验数据为准，
    # 防止模型错误改写概念名或来源文档 ID。
    raw_data["term"] = candidate.term
    raw_data["source_document_id"] = document.document_id
    raw_data["source_is_simulated"] = document.is_simulated

    try:
        return ConceptAnalysis.model_validate(raw_data)
    except ValidationError as exc:
        raise ConceptAnalysisError(
            f"模型分析结果字段校验失败：\n{exc}"
        ) from exc


def analyze_concept(
    document: PolicyDocument,
    candidate: ConceptCandidate,
    agent: AgentRunner | None = None,
    settings: LLMSettings | None = None,
) -> ConceptAnalysis:
    """调用 ConceptAnalysisAgent 分析一个候选概念。"""
    active_agent = (
        agent
        if agent is not None
        else build_concept_analysis_agent(settings)
    )

    input_text = build_analysis_input(
        document=document,
        candidate=candidate,
    )

    try:
        response = active_agent.run(input_text)
    except Exception as exc:
        raise ConceptAnalysisError(
            "ConceptAnalysisAgent 调用失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(response, str) or not response.strip():
        raise ConceptAnalysisError(
            "ConceptAnalysisAgent 返回了空结果"
        )

    return parse_concept_analysis_response(
        raw_response=response,
        document=document,
        candidate=candidate,
    )


def save_concept_analysis(
    analysis: ConceptAnalysis,
    output_path: str | Path,
) -> Path:
    """将结构化概念分析保存为 UTF-8 JSON 文件。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        analysis.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return path