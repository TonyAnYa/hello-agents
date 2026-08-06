"""使用历史用户反馈重新计算候选回答排名。"""

from __future__ import annotations

from collections.abc import Iterable

from enterprise_concept_radar.models import (
    AnswerFeedbackEvent,
    AnswerFeedbackSummary,
    AnswerPackage,
    BusinessImpactAssessment,
    FeedbackAwareRankingResult,
)
from enterprise_concept_radar.scoring.answer_ranking import (
    rank_answer_package,
)


def build_feedback_summaries(
    answer_ids: Iterable[str],
    events: Iterable[AnswerFeedbackEvent],
) -> list[AnswerFeedbackSummary]:
    """为每个候选回答生成反馈聚合结果。"""
    # 延迟导入，避免 scoring 与 tools 包初始化时互相导入。
    from enterprise_concept_radar.tools.feedback import (
        calculate_feedback_summary,
    )

    event_list = list(events)

    return [
        calculate_feedback_summary(
            answer_id=answer_id,
            events=event_list,
        )
        for answer_id in answer_ids
    ]


def rank_answer_package_with_feedback(
    package: AnswerPackage,
    impact_assessment: BusinessImpactAssessment,
    events: Iterable[AnswerFeedbackEvent],
    timeliness_score: float = 80,
) -> FeedbackAwareRankingResult:
    """将历史反馈分接入七项指标并重新排名。"""
    summaries = build_feedback_summaries(
        answer_ids=[
            candidate.answer_id
            for candidate in package.candidates
        ],
        events=events,
    )

    feedback_scores = {
        summary.answer_id: summary.user_feedback_score
        for summary in summaries
    }

    ranking = rank_answer_package(
        package=package,
        impact_assessment=impact_assessment,
        timeliness_score=timeliness_score,
        user_feedback_scores=feedback_scores,
    )

    return FeedbackAwareRankingResult(
        ranking=ranking,
        feedback_summaries=summaries,
    )