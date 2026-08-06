"""测试 AnswerComposerAgent 的结构化处理。"""

import json

import pytest

from enterprise_concept_radar.agents import (
    AnswerComposerError,
    compose_answer_package,
    parse_answer_composer_response,
)
from enterprise_concept_radar.config import SAMPLE_POLICY_DIR
from enterprise_concept_radar.models import (
    AnswerStyle,
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    ConceptAnalysis,
    ImpactLevel,
)
from enterprise_concept_radar.tools import (
    load_policy_directory,
)


def build_test_analysis() -> ConceptAnalysis:
    """创建测试概念分析。"""
    return ConceptAnalysis(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        explanation_draft="多个用户参与的绿电直连安排。",
        source_facts=[
            "输入材料提出探索多用户绿电直连协同机制。"
        ],
        rule_judgements=[
            "规则系统将其识别为新增说法。"
        ],
        model_inferences=[
            "该机制可能涉及跨用户计量协调。"
        ],
        related_term_comparison=[
            "该表述在绿电直连基础上增加多用户场景。"
        ],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        verification_actions=[
            "检索并核验真实政策原文。"
        ],
        confidence=0.8,
    )


def build_test_impact() -> BusinessImpactAssessment:
    """创建包含六个领域的测试业务影响。"""
    impacts = [
        BusinessDomainImpact(
            domain=domain,
            impact_level=ImpactLevel.MEDIUM,
            impact_summary=f"可能影响{domain.value}业务。",
            affected_processes=[f"{domain.value}业务流程"],
            risks=["责任边界需要核验"],
            opportunities=["促进跨专业协同"],
            recommended_actions=["组织专题研究"],
            evidence_basis=[
                "[模型推断] 可能影响现有业务规则"
            ],
        )
        for domain in BusinessDomain
    ]

    return BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="可能影响多个电网业务领域。",
        domain_impacts=impacts,
        cross_domain_issues=["多个专业需要协同"],
        governance_tasks=["建立概念词条"],
        uncertainties=[
            "当前来源为教学模拟数据，不能作为真实政策依据。"
        ],
        confidence=0.78,
    )


def build_fake_response(
    reverse_styles: bool = False,
    duplicate_styles: bool = False,
    include_warning: bool = True,
    conflicting_level: bool = False,
) -> str:
    """创建候选回答模拟响应。"""
    warning = (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
    )

    candidates = [
        {
            "answer_id": "answer-executive",
            "style": "管理摘要型",
            "title": "管理摘要",
            "content": (
                "多用户绿电直连是多个用户协同参与绿电直接供应"
                "的安排，当前属于分析草稿，可能影响计量和责任边界。"
            ),
            "evidence_references": [
                "[政策原文事实] 输入材料提出探索协同机制"
            ],
            "action_items": [
                "核验真实政策原文",
                "组织跨专业研究",
            ],
            "caveats": [warning] if include_warning else [],
        },
        {
            "answer_id": "answer-professional",
            "style": (
                "管理摘要型"
                if duplicate_styles
                else "专业分析型"
            ),
            "title": "专业分析",
            "content": (
                "该概念在绿电直连基础上增加多用户协同场景，"
                "可能影响规划、调度、交易、计量、安全和知识治理。"
            ),
            "evidence_references": [
                "[规则判断] 系统将其识别为新增说法",
                "[模型推断] 可能需要跨专业协调",
            ],
            "action_items": [
                "开展历史政策溯源",
                "评估业务规则影响",
            ],
            "caveats": [warning] if include_warning else [],
        },
    ]

    if conflicting_level:
        candidates[1]["content"] += (
        "安全责任：影响程度高。"
        )

    if reverse_styles:
        candidates.reverse()

    return json.dumps(
        {
            "question": "模型错误问题",
            "term": "模型错误术语",
            "source_document_id": "wrong-document-id",
            "source_is_simulated": False,
            "candidates": candidates,
        },
        ensure_ascii=False,
    )


def test_answer_composer_uses_local_identity_fields() -> None:
    """问题、概念和来源字段应以本地数据为准。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()
    impact = build_test_impact()

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            assert "管理摘要型" in input_text
            assert "专业分析型" in input_text
            assert kwargs["max_tokens"] == 3600
            return build_fake_response()

    package = compose_answer_package(
        question="多用户绿电直连对广东电网有什么影响？",
        document=document,
        analysis=analysis,
        impact_assessment=impact,
        agent=FakeAgent(),
    )

    assert package.question == (
        "多用户绿电直连对广东电网有什么影响？"
    )
    assert package.term == "多用户绿电直连"
    assert package.source_document_id == "demo-policy-2026-001"
    assert package.source_is_simulated is True


def test_simulation_warning_is_added_to_both_answers() -> None:
    """模拟数据警告缺失时应由本地程序补充。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]

    package = parse_answer_composer_response(
        raw_response=build_fake_response(
            include_warning=False
        ),
        question="测试问题",
        document=document,
        analysis=build_test_analysis(),
    )

    warning = (
        "当前来源为教学模拟数据，不能作为真实政策依据。"
    )

    assert all(
        warning in candidate.caveats
        for candidate in package.candidates
    )


def test_candidates_are_returned_in_fixed_style_order() -> None:
    """模型顺序不同也应整理为固定风格顺序。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]

    package = parse_answer_composer_response(
        raw_response=build_fake_response(
            reverse_styles=True
        ),
        question="测试问题",
        document=document,
        analysis=build_test_analysis(),
    )

    styles = [
        candidate.style
        for candidate in package.candidates
    ]

    assert styles == list(AnswerStyle)


def test_duplicate_styles_are_rejected() -> None:
    """两份回答使用同一风格时应拒绝结果。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]

    with pytest.raises(
        AnswerComposerError,
        match="候选回答字段校验失败",
    ):
        parse_answer_composer_response(
            raw_response=build_fake_response(
                duplicate_styles=True
            ),
            question="测试问题",
            document=document,
            analysis=build_test_analysis(),
        )
def test_answer_composer_retries_on_level_conflict() -> None:
    """回答影响等级与前序结果冲突时应自动重试。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
    analysis = build_test_analysis()
    impact = build_test_impact()

    calls: list[str] = []

    class FakeAgent:
        def run(
            self,
            input_text: str,
            **kwargs: object,
        ) -> str:
            calls.append(input_text)

            return build_fake_response(
                conflicting_level=len(calls) == 1
            )

    package = compose_answer_package(
        question="多用户绿电直连有什么影响？",
        document=document,
        analysis=analysis,
        impact_assessment=impact,
        agent=FakeAgent(),
    )

    assert len(calls) == 2
    assert "本地一致性校验发现" in calls[1]
    assert len(package.candidates) == 2