"""测试 EnterpriseConceptRadar 核心数据模型。"""

from datetime import date

from enterprise_concept_radar.models import (
    AnswerEvaluation,
    ConceptCandidate,
    ConceptCandidateType,
)


def test_concept_candidate_can_be_created() -> None:
    """候选概念应能够通过合法数据创建。"""
    candidate = ConceptCandidate(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        evidence_quote="文件提出探索多用户绿电直连协同机制。",
        candidate_type=ConceptCandidateType.NEW_CONCEPT,
        novelty_score=92,
        confidence=0.91,
        first_seen_date=date(2026, 8, 5),
        related_terms=["绿电直连"],
    )

    assert candidate.term == "多用户绿电直连"
    assert candidate.novelty_score == 92
    assert candidate.confidence == 0.91


def test_answer_evaluation_total_score() -> None:
    """回答适配度应按照固定权重计算。"""
    evaluation = AnswerEvaluation(
        question="多用户绿电直连是什么意思？",
        answer_id="answer-a",
        semantic_relevance=90,
        keyword_coverage=80,
        authority_score=95,
        timeliness_score=90,
        business_relevance=85,
        actionability_score=70,
        user_feedback_score=60,
    )

    expected_score = (
        90 * 0.25
        + 80 * 0.15
        + 95 * 0.20
        + 90 * 0.10
        + 85 * 0.15
        + 70 * 0.10
        + 60 * 0.05
    )

    assert evaluation.total_score == round(
        expected_score,
        2,
    )