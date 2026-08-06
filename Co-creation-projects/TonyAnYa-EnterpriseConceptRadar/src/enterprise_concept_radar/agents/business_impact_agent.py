"""广东电网业务影响分析智能体。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from enterprise_concept_radar.agents.concept_analysis_agent import (
    StructuredSimpleAgent,
    extract_json_object,
)
from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.models import (
    BusinessDomain,
    BusinessImpactAssessment,
    ConceptAnalysis,
    PolicyDocument,
)
from enterprise_concept_radar.services import (
    LLMSettings,
    build_llm,
)


class BusinessImpactError(RuntimeError):
    """业务影响分析或结构化结果解析失败。"""


class BusinessImpactRunner(Protocol):
    """BusinessImpactAgent 所需的最小运行接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回文本。"""


def load_business_impact_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取业务影响分析系统提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else CONFIG_DIR / "prompts" / "business_impact.md"
    )

    if not path.is_file():
        raise BusinessImpactError(
            f"业务影响提示词不存在：{path}"
        )

    try:
        content = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as exc:
        raise BusinessImpactError(
            f"无法读取业务影响提示词：{path}；{exc}"
        ) from exc

    if not content:
        raise BusinessImpactError(
            f"业务影响提示词为空：{path}"
        )

    return content


def build_business_impact_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建基于 HelloAgents 的业务影响智能体。"""
    active_settings = settings or LLMSettings.from_env()
    llm = build_llm(active_settings)

    return StructuredSimpleAgent(
        name="BusinessImpactAgent",
        llm=llm,
        system_prompt=load_business_impact_prompt(),
        enable_tool_calling=False,
    )


def build_business_impact_input(
    document: PolicyDocument,
    analysis: ConceptAnalysis,
) -> str:
    """构建发送给 BusinessImpactAgent 的结构化输入。"""
    payload = {
        "task": (
            "评估候选政策概念对广东电网六个业务领域的潜在影响"
        ),
        "required_domains": [
            domain.value
            for domain in BusinessDomain
        ],
        "policy_document": {
            "document_id": document.document_id,
            "title": document.title,
            "source_name": document.source_name,
            "published_date": document.published_date.isoformat(),
            "document_type": document.document_type.value,
            "is_simulated": document.is_simulated,
            "content": document.content,
        },
        "concept_analysis": {
            "term": analysis.term,
            "explanation_draft": analysis.explanation_draft,
            "source_facts": analysis.source_facts,
            "rule_judgements": analysis.rule_judgements,
            "model_inferences": analysis.model_inferences,
            "related_term_comparison": (
                analysis.related_term_comparison
            ),
            "uncertainties": analysis.uncertainties,
            "verification_actions": (
                analysis.verification_actions
            ),
            "confidence": analysis.confidence,
        },
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def parse_business_impact_response(
    raw_response: str,
    document: PolicyDocument,
    analysis: ConceptAnalysis,
) -> BusinessImpactAssessment:
    """解析并校验业务影响分析结果。"""
    raw_data = extract_json_object(raw_response)

    # 身份字段必须以本地已校验数据为准。
    raw_data["term"] = analysis.term
    raw_data["source_document_id"] = document.document_id
    raw_data["source_is_simulated"] = document.is_simulated

    uncertainties = list(
        raw_data.get("uncertainties") or []
    )

    simulation_warning = (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
    )

    if (
        document.is_simulated
        and simulation_warning not in uncertainties
    ):
        uncertainties.append(simulation_warning)

    raw_data["uncertainties"] = uncertainties

    try:
        assessment = BusinessImpactAssessment.model_validate(
            raw_data
        )
    except ValidationError as exc:
        raise BusinessImpactError(
            f"业务影响结果字段校验失败：\n{exc}"
        ) from exc

    actual_domains = {
        impact.domain
        for impact in assessment.domain_impacts
    }
    required_domains = set(BusinessDomain)
    missing_domains = required_domains - actual_domains

    if missing_domains:
        missing_text = "、".join(
            domain.value
            for domain in BusinessDomain
            if domain in missing_domains
        )

        raise BusinessImpactError(
            f"业务影响领域不完整，缺少：{missing_text}"
        )

    domain_order = {
        domain: index
        for index, domain in enumerate(BusinessDomain)
    }

    ordered_impacts = sorted(
        assessment.domain_impacts,
        key=lambda impact: domain_order[impact.domain],
    )

    return assessment.model_copy(
        update={
            "domain_impacts": ordered_impacts,
        }
    )


def assess_business_impact(
    document: PolicyDocument,
    analysis: ConceptAnalysis,
    agent: BusinessImpactRunner | None = None,
    settings: LLMSettings | None = None,
) -> BusinessImpactAssessment:
    """调用 BusinessImpactAgent 生成业务影响评估。"""
    active_agent = (
        agent
        if agent is not None
        else build_business_impact_agent(settings)
    )

    input_text = build_business_impact_input(
        document=document,
        analysis=analysis,
    )

    try:
        response = active_agent.run(
            input_text,
            max_tokens=3200,
        )
    except Exception as exc:
        raise BusinessImpactError(
            "BusinessImpactAgent 调用失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(response, str) or not response.strip():
        raise BusinessImpactError(
            "BusinessImpactAgent 返回了空结果"
        )

    return parse_business_impact_response(
        raw_response=response,
        document=document,
        analysis=analysis,
    )


def save_business_impact(
    assessment: BusinessImpactAssessment,
    output_path: str | Path,
) -> Path:
    """将业务影响评估保存为 UTF-8 JSON 文件。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        assessment.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return path