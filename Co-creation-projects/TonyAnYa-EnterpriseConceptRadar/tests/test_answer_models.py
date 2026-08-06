"""测试候选回答数据模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerStyle,
)


def build_candidate(
    answer_id: str,
    style: AnswerStyle,
) -> AnswerCandidate:
    """创建测试候选回答。"""
    return AnswerCandidate(
        answer_id=answer_id,
        style=style,
        title="多用户绿电直连分析",
        content=(
            "多用户绿电直连是多个用户协同参与绿色电力"
            "直接供应的一种安排，可能影响电网业务流程。"
        ),
        evidence_references=[
            "教学模拟政策原文",
        ],
        action_items=[
            "核验真实政策原文",
        ],
        caveats=[
            "当前来源为教学模拟数据",
        ],
    )


def test_answer_package_requires_two_styles() -> None:
    """两份不同风格的回答应能组成回答包。"""
    package = AnswerPackage(
        question="多用户绿电直连是什么意思？",
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        candidates=[
            build_candidate(
                "answer-a",
                AnswerStyle.EXECUTIVE_BRIEF,
            ),
            build_candidate(
                "answer-b",
                AnswerStyle.PROFESSIONAL_ANALYSIS,
            ),
        ],
    )

    assert len(package.candidates) == 2


def test_duplicate_answer_ids_are_rejected() -> None:
    """候选回答 ID 不能重复。"""
    with pytest.raises(
        ValidationError,
        match="answer_id 必须不同",
    ):
        AnswerPackage(
            question="测试问题",
            term="测试概念",
            source_document_id="demo-1",
            source_is_simulated=True,
            candidates=[
                build_candidate(
                    "same-id",
                    AnswerStyle.EXECUTIVE_BRIEF,
                ),
                build_candidate(
                    "same-id",
                    AnswerStyle.PROFESSIONAL_ANALYSIS,
                ),
            ],
        )