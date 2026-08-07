"""使用搜索候选和 LLM 判断政策源官方网站。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from pydantic import ValidationError

from enterprise_concept_radar.agents.concept_analysis_agent import (
    StructuredSimpleAgent,
    extract_json_object,
)
from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.policy_sources import (
    PolicySourceResolution,
    PolicySourceResolverDecision,
    PolicySourceSearchCandidate,
)
from enterprise_concept_radar.services import (
    LLMSettings,
    build_llm,
)


class PolicySourceResolverError(RuntimeError):
    """政策源 LLM 解析失败。"""


class PolicySourceResolverRunner(Protocol):
    """政策源解析 Agent 所需的最小接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回字符串。"""


def load_policy_source_resolver_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取政策源解析提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else (
            CONFIG_DIR
            / "prompts"
            / "policy_source_resolver.md"
        )
    )

    if not path.is_file():
        raise PolicySourceResolverError(
            f"政策源解析提示词不存在：{path}"
        )

    content = path.read_text(
        encoding="utf-8",
    ).strip()

    if not content:
        raise PolicySourceResolverError(
            f"政策源解析提示词为空：{path}"
        )

    return content


def build_policy_source_resolver_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建政策源解析智能体。"""
    active_settings = settings or LLMSettings.from_env()

    return StructuredSimpleAgent(
        name="PolicySourceResolverAgent",
        llm=build_llm(active_settings),
        system_prompt=load_policy_source_resolver_prompt(),
        enable_tool_calling=False,
    )


def build_policy_source_resolver_input(
    requested_name: str,
    candidates: list[PolicySourceSearchCandidate],
) -> str:
    """构建来源解析 Agent 的输入。"""
    payload = {
        "requested_name": requested_name,
        "candidates": [
            {
                "index": index,
                "title": candidate.title,
                "url": candidate.url,
                "snippet": candidate.snippet,
            }
            for index, candidate in enumerate(candidates)
        ],
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def parse_policy_source_resolution(
    requested_name: str,
    candidates: list[PolicySourceSearchCandidate],
    raw_response: str,
    minimum_confidence: float = 0.6,
) -> PolicySourceResolution:
    """解析 LLM 决策并锁定搜索结果中的网址。"""
    try:
        decision = PolicySourceResolverDecision.model_validate(
            extract_json_object(raw_response)
        )
    except ValidationError as exc:
        raise PolicySourceResolverError(
            f"政策源解析结果字段无效：\n{exc}"
        ) from exc

    index = decision.selected_candidate_index

    if index >= len(candidates):
        raise PolicySourceResolverError(
            "LLM 选择的候选索引超出范围"
        )

    if decision.confidence < minimum_confidence:
        raise PolicySourceResolverError(
            "政策源匹配置信度过低："
            f"{decision.confidence:.2f}"
        )

    selected = candidates[index]
    domain = urlparse(selected.url).netloc

    return PolicySourceResolution(
        requested_name=requested_name,
        official_name=decision.official_name,
        entry_url=selected.url,
        source_domain=domain,
        confidence=decision.confidence,
        reason=decision.reason,
    )


def resolve_policy_source(
    requested_name: str,
    candidates: list[PolicySourceSearchCandidate],
    agent: PolicySourceResolverRunner | None = None,
    settings: LLMSettings | None = None,
) -> PolicySourceResolution:
    """调用 LLM 从搜索候选中选择官方网站。"""
    if not candidates:
        raise PolicySourceResolverError(
            "政策源搜索候选不能为空"
        )

    active_agent = (
        agent
        if agent is not None
        else build_policy_source_resolver_agent(settings)
    )

    response = active_agent.run(
        build_policy_source_resolver_input(
            requested_name=requested_name,
            candidates=candidates,
        ),
        max_tokens=900,
    )

    if not isinstance(response, str) or not response.strip():
        raise PolicySourceResolverError(
            "PolicySourceResolverAgent 返回了空结果"
        )

    return parse_policy_source_resolution(
        requested_name=requested_name,
        candidates=candidates,
        raw_response=response,
    )