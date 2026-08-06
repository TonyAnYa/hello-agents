"""测试回答推荐结果模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    AnswerEvaluation,
    AnswerRankingResult,
)


def build_evaluation(
    answer_id: str,
) -> AnswerEvaluation:
    """创建测试评分结果。"""
    return AnswerEvaluation(
        question="测试问题",
        answer_id=answer_id,
        semantic_relevance=80,
        keyword_coverage=70,
        authority_score=55,
        timeliness_score=80,
        business_relevance=60,
        actionability_score=75,
        user_feedback_score=50,
        comments=["测试评分"],
    )


def test_answer_ranking_result_can_be_created() -> None:
    """合法推荐结果应通过校验。"""
    result = AnswerRankingResult(
        question="多用户绿电直连有什么影响？",
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        required_keywords=[
            "多用户绿电直连",
            "计量结算",
        ],
        evaluations=[
            build_evaluation("answer-a"),
            build_evaluation("answer-b"),
        ],
        recommended_answer_id="answer-a",
        recommendation_reason="answer-a 总分更高。",
    )

    assert result.recommended_answer_id == "answer-a"
    assert len(result.evaluations) == 2


def test_unknown_recommended_answer_is_rejected() -> None:
    """推荐 ID 不在评分结果中时应拒绝数据。"""
    with pytest.raises(
        ValidationError,
        match="recommended_answer_id 不在评分结果中",
    ):
        AnswerRankingResult(
            question="测试问题",
            term="测试概念",
            source_document_id="demo-1",
            source_is_simulated=True,
            evaluations=[
                build_evaluation("answer-a"),
                build_evaluation("answer-b"),
            ],
            recommended_answer_id="answer-c",
            recommendation_reason="错误测试。",
        )
def test_answer_ranking_result_can_round_trip_json() -> None:
    """排名结果保存为 JSON 后应能重新读取。"""
    result = AnswerRankingResult(
        question="多用户绿电直连有什么影响？",
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        required_keywords=[
            "多用户绿电直连",
            "计量结算",
        ],
        evaluations=[
            build_evaluation("answer-a"),
            build_evaluation("answer-b"),
        ],
        recommended_answer_id="answer-a",
        recommendation_reason="answer-a 总分更高。",
    )

    json_text = result.model_dump_json(
        exclude_computed_fields=True,
    )

    restored = AnswerRankingResult.model_validate_json(
        json_text
    )

    assert restored.recommended_answer_id == "answer-a"
    assert len(restored.evaluations) == 2
    assert (
        restored.evaluations[0].total_score
        == result.evaluations[0].total_score
    )