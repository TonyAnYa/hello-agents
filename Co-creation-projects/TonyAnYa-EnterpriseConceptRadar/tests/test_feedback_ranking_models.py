"""测试反馈感知排名结果模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    AnswerEvaluation,
    AnswerFeedbackSummary,
    AnswerRankingResult,
    FeedbackAwareRankingResult,
)


def build_evaluation(
    answer_id: str,
) -> AnswerEvaluation:
    """创建测试评分。"""
    return AnswerEvaluation(
        question="测试问题",
        answer_id=answer_id,
        semantic_relevance=80,
        keyword_coverage=80,
        authority_score=55,
        timeliness_score=80,
        business_relevance=80,
        actionability_score=80,
        user_feedback_score=50,
    )


def build_ranking() -> AnswerRankingResult:
    """创建测试排名。"""
    return AnswerRankingResult(
        question="测试问题",
        term="测试概念",
        source_document_id="demo-1",
        source_is_simulated=True,
        evaluations=[
            build_evaluation("answer-a"),
            build_evaluation("answer-b"),
        ],
        recommended_answer_id="answer-a",
        recommendation_reason="answer-a 得分较高。",
    )


def build_summary(
    answer_id: str,
) -> AnswerFeedbackSummary:
    """创建测试反馈汇总。"""
    return AnswerFeedbackSummary(
        answer_id=answer_id,
        total_events=0,
        user_feedback_score=50,
    )


def test_feedback_aware_ranking_can_be_created() -> None:
    """排名和两份反馈汇总一致时应通过校验。"""
    result = FeedbackAwareRankingResult(
        ranking=build_ranking(),
        feedback_summaries=[
            build_summary("answer-a"),
            build_summary("answer-b"),
        ],
    )

    assert len(result.feedback_summaries) == 2


def test_mismatched_feedback_ids_are_rejected() -> None:
    """反馈汇总与排名回答不一致时应拒绝数据。"""
    with pytest.raises(
        ValidationError,
        match="answer_id 不一致",
    ):
        FeedbackAwareRankingResult(
            ranking=build_ranking(),
            feedback_summaries=[
                build_summary("answer-a"),
                build_summary("answer-c"),
            ],
        )