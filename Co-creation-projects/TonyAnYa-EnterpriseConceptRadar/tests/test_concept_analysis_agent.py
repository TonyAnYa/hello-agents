"""测试 ConceptAnalysisAgent 的结构化解析。"""

import json

from enterprise_concept_radar.agents import (
    analyze_concept,
    extract_json_object,
)
from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    CONFIG_DIR,
    SAMPLE_POLICY_DIR,
)
from enterprise_concept_radar.scoring import (
    load_concept_baseline,
)
from enterprise_concept_radar.tools import (
    extract_concept_candidates,
    load_concept_rules,
    load_policy_directory,
)


def build_document_and_candidate():
    """读取教学样本及第一个候选概念。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    baseline = load_concept_baseline(
        BASELINE_DATA_DIR / "known_terms.json"
    )
    rules = load_concept_rules(
        CONFIG_DIR / "concept_rules.yaml"
    )
    candidates = extract_concept_candidates(
        document=document,
        baseline=baseline,
        rules=rules,
    )

    candidate = next(
        item
        for item in candidates
        if item.term == "多用户绿电直连"
    )

    return document, candidate


def build_fake_response() -> str:
    """创建不需要在线模型的模拟响应。"""
    data = {
        "term": "错误的模型术语",
        "source_document_id": "wrong-document-id",
        "source_is_simulated": False,
        "explanation_draft": (
            "该概念可暂时理解为多个用户参与的绿电直连安排。"
        ),
        "source_facts": [
            "输入材料提出探索多用户绿电直连协同机制。"
        ],
        "rule_judgements": [
            "规则系统将其识别为新增说法，新颖度为82分。"
        ],
        "model_inferences": [
            "该机制可能涉及计量和责任边界协调。"
        ],
        "related_term_comparison": [
            "它与绿电直连相关，但增加了多用户协同场景。"
        ],
        "uncertainties": [
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        "verification_actions": [
            "检索权威机构发布的真实政策原文。"
        ],
        "confidence": 0.72,
    }

    return (
        "```json\n"
        + json.dumps(
            data,
            ensure_ascii=False,
        )
        + "\n```"
    )


def test_extract_json_object_from_code_fence() -> None:
    """应能从代码围栏中提取 JSON。"""
    parsed = extract_json_object(
        build_fake_response()
    )

    assert parsed["confidence"] == 0.72


def test_analysis_uses_local_identity_fields() -> None:
    """概念名和来源 ID 应以本地校验数据为准。"""
    document, candidate = build_document_and_candidate()

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            assert '"is_simulated": true' in input_text
            assert "多用户绿电直连" in input_text
            return build_fake_response()

    analysis = analyze_concept(
        document=document,
        candidate=candidate,
        agent=FakeAgent(),
    )

    assert analysis.term == "多用户绿电直连"
    assert (
        analysis.source_document_id
        == "demo-policy-2026-001"
    )
    assert analysis.source_is_simulated is True


def test_analysis_separates_information_types() -> None:
    """结果应分别保存事实、规则判断和模型推断。"""
    document, candidate = build_document_and_candidate()

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            return build_fake_response()

    analysis = analyze_concept(
        document=document,
        candidate=candidate,
        agent=FakeAgent(),
    )

    assert analysis.source_facts
    assert analysis.rule_judgements
    assert analysis.model_inferences
    assert "教学模拟数据" in analysis.uncertainties[0]
def test_structured_agent_returns_llm_response() -> None:
    """结构化 Agent 应直接返回底层 LLM 的文本。"""
    from enterprise_concept_radar.agents import (
        StructuredSimpleAgent,
    )

    captured_messages: list[dict[str, str]] = []

    class FakeLLM:
        def invoke(
            self,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            captured_messages.extend(messages)
            return '  {"status": "ok"}  '

    agent = StructuredSimpleAgent(
        name="TestStructuredAgent",
        llm=FakeLLM(),
        system_prompt="只输出 JSON。",
        enable_tool_calling=False,
    )

    response = agent.run(
        "执行测试。",
    )

    assert response == '{"status": "ok"}'
    assert captured_messages == [
        {
            "role": "system",
            "content": "只输出 JSON。",
        },
        {
            "role": "user",
            "content": "执行测试。",
        },
    ]
def test_structured_agent_uses_json_mode_and_retries() -> None:
    """结构化 Agent 应关闭思考模式，并在空响应时重试。"""
    from enterprise_concept_radar.agents import (
        StructuredSimpleAgent,
    )

    calls: list[
        tuple[
            list[dict[str, str]],
            dict[str, object],
        ]
    ] = []

    class FakeLLM:
        def invoke(
            self,
            messages: list[dict[str, str]],
            **kwargs: object,
        ) -> str:
            calls.append(
                (
                    messages,
                    kwargs,
                )
            )

            if len(calls) == 1:
                return ""

            return '{"status":"ok"}'

    agent = StructuredSimpleAgent(
        name="TestStructuredAgent",
        llm=FakeLLM(),
        system_prompt="只输出 JSON。",
        enable_tool_calling=False,
    )

    response = agent.run(
        "执行结构化测试。",
    )

    assert response == '{"status":"ok"}'
    assert len(calls) == 2

    first_kwargs = calls[0][1]

    assert first_kwargs["response_format"] == {
        "type": "json_object",
    }
    assert first_kwargs["extra_body"] == {
        "thinking": {
            "type": "disabled",
        }
    }

    retry_messages = calls[1][0]

    assert "上一次没有返回最终内容" in (
        retry_messages[-1]["content"]
    )