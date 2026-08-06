"""测试候选概念新颖度评分。"""

from datetime import date

from enterprise_concept_radar.models import (
    BaselineTerm,
    ConceptBaseline,
    ConceptCandidateType,
)
from enterprise_concept_radar.scoring import (
    assess_term_novelty,
)


def build_test_baseline() -> ConceptBaseline:
    """创建测试术语基线。"""
    return ConceptBaseline(
        baseline_name="测试基线",
        version="test-1",
        known_terms=[
            BaselineTerm(
                term="绿电直连",
                first_seen_date=date(2025, 1, 1),
                aliases=["绿色电力直接供应"],
                source="测试数据",
            )
        ],
    )


def test_exact_known_term_is_heating_concept() -> None:
    """完全匹配的术语应视为已有概念再次出现。"""
    assessment = assess_term_novelty(
        "绿电直连",
        build_test_baseline(),
    )

    assert assessment.score == 25
    assert (
        assessment.candidate_type
        == ConceptCandidateType.HEATING_CONCEPT
    )
    assert assessment.first_seen_date == date(
        2025,
        1,
        1,
    )


def test_extended_term_is_new_expression() -> None:
    """包含已有术语的新表述应视为新增说法。"""
    assessment = assess_term_novelty(
        "多用户绿电直连",
        build_test_baseline(),
    )

    assert assessment.score == 82
    assert (
        assessment.candidate_type
        == ConceptCandidateType.NEW_EXPRESSION
    )
    assert assessment.related_terms == (
        "绿电直连",
    )


def test_unrelated_term_is_new_concept_candidate() -> None:
    """无历史关联的术语应进入新增概念候选。"""
    assessment = assess_term_novelty(
        "电碳协同调度",
        build_test_baseline(),
    )

    assert assessment.score == 92
    assert (
        assessment.candidate_type
        == ConceptCandidateType.NEW_CONCEPT
    )