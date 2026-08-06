"""两份候选回答的自动评分与推荐。"""

from __future__ import annotations

from collections.abc import Mapping

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerRankingResult,
    BusinessDomain,
    BusinessImpactAssessment,
)
from enterprise_concept_radar.scoring.answer_fit import (
    normalize_text,
    score_answer_candidate,
)


class AnswerRankingError(ValueError):
    """候选回答排名输入无效。"""


def build_required_keywords(
    term: str,
    impact_assessment: BusinessImpactAssessment,
) -> list[str]:
    """根据概念和业务影响领域构建评分关键词。"""
    keywords = [term]

    keywords.extend(
        impact.domain.value
        for impact in impact_assessment.domain_impacts
    )

    return list(dict.fromkeys(keywords))


def count_covered_business_domains(
    candidate: AnswerCandidate,
) -> int:
    """统计回答正文覆盖的广东电网业务领域数量。"""
    normalized_content = normalize_text(
        candidate.content
    )

    return sum(
        normalize_text(domain.value) in normalized_content
        for domain in BusinessDomain
    )


def validate_ranking_inputs(
    package: AnswerPackage,
    impact_assessment: BusinessImpactAssessment,
) -> None:
    """校验回答包与业务影响评估是否属于同一任务。"""
    if package.term != impact_assessment.term:
        raise AnswerRankingError(
            "回答包与业务影响评估的 term 不一致"
        )

    if (
        package.source_document_id
        != impact_assessment.source_document_id
    ):
        raise AnswerRankingError(
            "回答包与业务影响评估的来源文档不一致"
        )

    if (
        package.source_is_simulated
        != impact_assessment.source_is_simulated
    ):
        raise AnswerRankingError(
            "回答包与业务影响评估的来源性质不一致"
        )


def rank_answer_package(
    package: AnswerPackage,
    impact_assessment: BusinessImpactAssessment,
    timeliness_score: float = 80,
    user_feedback_scores: Mapping[str, float] | None = None,
) -> AnswerRankingResult:
    """对两份候选回答评分并推荐总分更高的版本。"""
    validate_ranking_inputs(
        package=package,
        impact_assessment=impact_assessment,
    )

    required_keywords = build_required_keywords(
        term=package.term,
        impact_assessment=impact_assessment,
    )
    feedback_scores = user_feedback_scores or {}

    evaluations = [
        score_answer_candidate(
            question=package.question,
            term=package.term,
            candidate=candidate,
            required_keywords=required_keywords,
            source_is_simulated=package.source_is_simulated,
            covered_domain_count=(
                count_covered_business_domains(
                    candidate
                )
            ),
            timeliness_score=timeliness_score,
            user_feedback_score=feedback_scores.get(
                candidate.answer_id,
                50,
            ),
        )
        for candidate in package.candidates
    ]

    ordered_evaluations = sorted(
        evaluations,
        key=lambda evaluation: (
            evaluation.total_score,
            evaluation.semantic_relevance,
            evaluation.actionability_score,
            evaluation.answer_id,
        ),
        reverse=True,
    )

    recommended = ordered_evaluations[0]
    runner_up = ordered_evaluations[1]
    score_difference = round(
        recommended.total_score
        - runner_up.total_score,
        2,
    )

    reason = (
        f"推荐回答 {recommended.answer_id}，"
        f"总分为 {recommended.total_score:.2f}，"
        f"较另一回答高 {score_difference:.2f} 分。"
        f"其语义相关性为 "
        f"{recommended.semantic_relevance:.2f}，"
        f"业务关联度为 "
        f"{recommended.business_relevance:.2f}，"
        f"可操作性为 "
        f"{recommended.actionability_score:.2f}。"
    )

    if package.source_is_simulated:
        reason += (
            "当前权威依据得分受到教学模拟来源上限约束，"
            "推荐结果仅用于演示。"
        )

    return AnswerRankingResult(
        question=package.question,
        term=package.term,
        source_document_id=package.source_document_id,
        source_is_simulated=package.source_is_simulated,
        required_keywords=required_keywords,
        evaluations=ordered_evaluations,
        recommended_answer_id=recommended.answer_id,
        recommendation_reason=reason,
    )