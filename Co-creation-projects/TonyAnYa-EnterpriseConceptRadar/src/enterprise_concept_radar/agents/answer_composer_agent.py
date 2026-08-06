"""候选回答生成智能体。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from enterprise_concept_radar.agents.concept_analysis_agent import (
    StructuredSimpleAgent,
    extract_json_object,
)
from enterprise_concept_radar.config import CONFIG_DIR
from enterprise_concept_radar.models import (
    AnswerPackage,
    AnswerStyle,
    BusinessImpactAssessment,
    ConceptAnalysis,
    PolicyDocument,
)
from enterprise_concept_radar.services import (
    LLMSettings,
    build_llm,
)


class AnswerComposerError(RuntimeError):
    """候选回答生成或结构化结果解析失败。"""


class AnswerComposerRunner(Protocol):
    """AnswerComposerAgent 所需的最小运行接口。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        """运行 Agent 并返回文本。"""


def load_answer_composer_prompt(
    prompt_path: str | Path | None = None,
) -> str:
    """读取候选回答生成提示词。"""
    path = (
        Path(prompt_path)
        if prompt_path is not None
        else CONFIG_DIR / "prompts" / "answer_composer.md"
    )

    if not path.is_file():
        raise AnswerComposerError(
            f"回答生成提示词不存在：{path}"
        )

    try:
        content = path.read_text(
            encoding="utf-8",
        ).strip()
    except OSError as exc:
        raise AnswerComposerError(
            f"无法读取回答生成提示词：{path}；{exc}"
        ) from exc

    if not content:
        raise AnswerComposerError(
            f"回答生成提示词为空：{path}"
        )

    return content


def build_answer_composer_agent(
    settings: LLMSettings | None = None,
) -> StructuredSimpleAgent:
    """创建基于 HelloAgents 的候选回答生成智能体。"""
    active_settings = settings or LLMSettings.from_env()
    llm = build_llm(active_settings)

    return StructuredSimpleAgent(
        name="AnswerComposerAgent",
        llm=llm,
        system_prompt=load_answer_composer_prompt(),
        enable_tool_calling=False,
    )


def build_answer_composer_input(
    question: str,
    document: PolicyDocument,
    analysis: ConceptAnalysis,
    impact_assessment: BusinessImpactAssessment,
) -> str:
    """构建发送给 AnswerComposerAgent 的结构化输入。"""
    payload = {
        "task": "针对用户问题生成两份不同风格的候选回答",
        "question": question,
        "required_styles": [
            style.value
            for style in AnswerStyle
        ],
        "required_impact_levels": {
            impact.domain.value: impact.impact_level.value
            for impact in impact_assessment.domain_impacts
        },
        "policy_document": {
            "document_id": document.document_id,
            "title": document.title,
            "source_name": document.source_name,
            "published_date": document.published_date.isoformat(),
            "document_type": document.document_type.value,
            "is_simulated": document.is_simulated,
            "content": document.content,
        },
        "concept_analysis": analysis.model_dump(
            mode="json",
        ),
        "business_impact_assessment": (
            impact_assessment.model_dump(
                mode="json",
            )
        ),
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def parse_answer_composer_response(
    raw_response: str,
    question: str,
    document: PolicyDocument,
    analysis: ConceptAnalysis,
) -> AnswerPackage:
    """解析并校验两份候选回答。"""
    raw_data = extract_json_object(raw_response)

    # 核心身份字段以本地已校验数据为准。
    raw_data["question"] = question
    raw_data["term"] = analysis.term
    raw_data["source_document_id"] = document.document_id
    raw_data["source_is_simulated"] = document.is_simulated

    candidates = raw_data.get("candidates")

    if not isinstance(candidates, list):
        raise AnswerComposerError(
            "模型结果中 candidates 必须是列表"
        )

    simulation_warning = (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
    )

    normalized_candidates: list[object] = []

    for candidate in candidates:
        if not isinstance(candidate, dict):
            normalized_candidates.append(candidate)
            continue

        normalized_candidate = dict(candidate)
        caveats = list(
            normalized_candidate.get("caveats") or []
        )

        if (
            document.is_simulated
            and simulation_warning not in caveats
        ):
            caveats.append(simulation_warning)

        normalized_candidate["caveats"] = caveats
        normalized_candidates.append(
            normalized_candidate
        )

    raw_data["candidates"] = normalized_candidates

    try:
        package = AnswerPackage.model_validate(
            raw_data
        )
    except ValidationError as exc:
        raise AnswerComposerError(
            f"候选回答字段校验失败：\n{exc}"
        ) from exc

    actual_styles = {
        candidate.style
        for candidate in package.candidates
    }
    required_styles = set(AnswerStyle)

    if actual_styles != required_styles:
        missing_styles = required_styles - actual_styles
        missing_text = "、".join(
            style.value
            for style in AnswerStyle
            if style in missing_styles
        )

        raise AnswerComposerError(
            f"候选回答风格不完整，缺少：{missing_text}"
        )

    style_order = {
        style: index
        for index, style in enumerate(AnswerStyle)
    }
    ordered_candidates = sorted(
        package.candidates,
        key=lambda candidate: style_order[candidate.style],
    )

    return package.model_copy(
        update={
            "candidates": ordered_candidates,
        }
    )

def find_impact_level_conflicts(
    package: AnswerPackage,
    impact_assessment: BusinessImpactAssessment,
) -> list[str]:
    """检查回答中明确描述的影响等级是否与前序评估一致。

    当前只检查回答明确出现的：
    “某业务领域……影响程度：高/中/低/待核验”。

    没有明确描述影响等级的段落不会被判定为冲突。
    """
    expected_levels = {
        impact.domain.value: impact.impact_level.value
        for impact in impact_assessment.domain_impacts
    }

    conflicts: list[str] = []

    for candidate in package.candidates:
        compact_content = re.sub(
            r"\s+",
            "",
            candidate.content,
        )

        for domain, expected_level in expected_levels.items():
            pattern = (
                rf"{re.escape(domain)}"
                rf"[^。；\n]{{0,40}}"
                rf"影响程度[:：]?"
                rf"(待核验|高|中|低)"
            )

            match = re.search(
                pattern,
                compact_content,
            )

            if match is None:
                continue

            actual_level = match.group(1)

            if actual_level != expected_level:
                conflicts.append(
                    f"{candidate.style.value}回答中，"
                    f"“{domain}”的影响程度为“{actual_level}”，"
                    f"但前序评估结果为“{expected_level}”。"
                )

    return conflicts

def compose_answer_package(
    question: str,
    document: PolicyDocument,
    analysis: ConceptAnalysis,
    impact_assessment: BusinessImpactAssessment,
    agent: AnswerComposerRunner | None = None,
    settings: LLMSettings | None = None,
) -> AnswerPackage:
    """调用 AnswerComposerAgent 生成两份候选回答。

    当回答明确写出的影响等级与前序评估冲突时，
    系统会携带冲突信息自动重试一次。
    """
    cleaned_question = question.strip()

    if not cleaned_question:
        raise AnswerComposerError(
            "用户问题不能为空"
        )

    active_agent = (
        agent
        if agent is not None
        else build_answer_composer_agent(settings)
    )

    base_input = build_answer_composer_input(
        question=cleaned_question,
        document=document,
        analysis=analysis,
        impact_assessment=impact_assessment,
    )

    last_conflicts: list[str] = []

    for attempt in range(2):
        active_input = base_input

        if attempt == 1:
            conflict_text = "\n".join(
                f"- {item}"
                for item in last_conflicts
            )

            active_input += (
                "\n\n本地一致性校验发现上一版回答存在以下冲突：\n"
                f"{conflict_text}\n"
                "请重新生成完整 JSON。"
                "所有业务影响等级必须严格采用 "
                "required_impact_levels 中的值。"
            )

        try:
            response = active_agent.run(
                active_input,
                max_tokens=3600,
            )
        except Exception as exc:
            raise AnswerComposerError(
                "AnswerComposerAgent 调用失败："
                f"{type(exc).__name__}: {exc}"
            ) from exc

        if not isinstance(response, str) or not response.strip():
            raise AnswerComposerError(
                "AnswerComposerAgent 返回了空结果"
            )

        package = parse_answer_composer_response(
            raw_response=response,
            question=cleaned_question,
            document=document,
            analysis=analysis,
        )

        conflicts = find_impact_level_conflicts(
            package=package,
            impact_assessment=impact_assessment,
        )

        if not conflicts:
            return package

        last_conflicts = conflicts

    raise AnswerComposerError(
        "候选回答连续两次与前序业务影响评估不一致：\n"
        + "\n".join(last_conflicts)
    )
def save_answer_package(
    package: AnswerPackage,
    output_path: str | Path,
) -> Path:
    """将候选回答包保存为 UTF-8 JSON 文件。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        package.model_dump_json(indent=2),
        encoding="utf-8",
    )

    return path