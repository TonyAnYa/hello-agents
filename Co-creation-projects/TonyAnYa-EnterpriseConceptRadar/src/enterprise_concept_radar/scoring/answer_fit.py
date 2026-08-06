"""候选回答与用户问题的适配度评分。"""

from __future__ import annotations

import re

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerEvaluation,
)


class AnswerFitScoringError(ValueError):
    """回答适配度评分输入无效。"""


def normalize_text(text: str) -> str:
    """移除空白和常见标点，便于进行简单文本比较。"""
    return re.sub(
        r"""[\s\-—_·（）()《》“”"'，,。！？；：:]""",
        "",
        text,
    ).casefold()


def build_bigrams(text: str) -> set[str]:
    """将文本拆分为相邻双字符集合。"""
    normalized = normalize_text(text)

    if len(normalized) < 2:
        return {normalized} if normalized else set()

    return {
        normalized[index : index + 2]
        for index in range(len(normalized) - 1)
    }


def estimate_semantic_relevance(
    question: str,
    answer: str,
    term: str,
) -> float:
    """通过术语命中和双字符覆盖估算语义相关性。

    该评分只作为 MVP 的透明规则评分，
    后续可替换为向量相似度或专门的评估 Agent。
    """
    question_bigrams = build_bigrams(question)
    answer_bigrams = build_bigrams(answer)

    if not question_bigrams:
        raise AnswerFitScoringError(
            "问题不能为空"
        )

    overlap_ratio = (
        len(question_bigrams & answer_bigrams)
        / len(question_bigrams)
    )

    score = overlap_ratio * 70

    if normalize_text(term) in normalize_text(answer):
        score += 30

    return round(
        min(score, 100),
        2,
    )


def calculate_keyword_coverage(
    answer: str,
    required_keywords: list[str],
) -> float:
    """计算必要关键词在回答中的覆盖比例。"""
    cleaned_keywords = [
        keyword.strip()
        for keyword in required_keywords
        if keyword.strip()
    ]

    if not cleaned_keywords:
        return 100.0

    normalized_answer = normalize_text(answer)

    covered_count = sum(
        normalize_text(keyword) in normalized_answer
        for keyword in cleaned_keywords
    )

    return round(
        covered_count
        / len(cleaned_keywords)
        * 100,
        2,
    )


def calculate_authority_score(
    evidence_references: list[str],
    source_is_simulated: bool,
) -> float:
    """根据证据数量和来源性质计算权威依据得分。"""
    evidence_count = len(
        [
            reference
            for reference in evidence_references
            if reference.strip()
        ]
    )

    if evidence_count >= 3:
        score = 95.0
    elif evidence_count == 2:
        score = 85.0
    elif evidence_count == 1:
        score = 65.0
    else:
        score = 20.0

    # 教学模拟数据不得获得高权威分。
    if source_is_simulated:
        score = min(score, 55.0)

    return score


def calculate_business_relevance(
    covered_domain_count: int,
) -> float:
    """按六个广东电网业务领域计算覆盖度。"""
    if covered_domain_count < 0:
        raise AnswerFitScoringError(
            "业务领域数量不能小于 0"
        )

    return round(
        min(covered_domain_count, 6)
        / 6
        * 100,
        2,
    )


def calculate_actionability(
    action_items: list[str],
) -> float:
    """根据有效行动建议数量计算可操作性。"""
    valid_actions = [
        item
        for item in action_items
        if item.strip()
    ]

    return float(
        min(len(valid_actions) * 25, 100)
    )


def score_answer_candidate(
    question: str,
    term: str,
    candidate: AnswerCandidate,
    required_keywords: list[str],
    source_is_simulated: bool,
    covered_domain_count: int,
    timeliness_score: float = 80,
    user_feedback_score: float = 50,
) -> AnswerEvaluation:
    """按照项目七项指标对一个候选回答评分。"""
    return AnswerEvaluation(
        question=question,
        answer_id=candidate.answer_id,
        semantic_relevance=estimate_semantic_relevance(
            question=question,
            answer=candidate.content,
            term=term,
        ),
        keyword_coverage=calculate_keyword_coverage(
            answer=candidate.content,
            required_keywords=required_keywords,
        ),
        authority_score=calculate_authority_score(
            evidence_references=(
                candidate.evidence_references
            ),
            source_is_simulated=source_is_simulated,
        ),
        timeliness_score=timeliness_score,
        business_relevance=calculate_business_relevance(
            covered_domain_count
        ),
        actionability_score=calculate_actionability(
            candidate.action_items
        ),
        user_feedback_score=user_feedback_score,
        comments=[
            "语义相关性使用透明文本规则估算。",
            (
                "权威依据得分已根据教学模拟来源设置上限。"
                if source_is_simulated
                else "权威依据得分根据证据数量计算。"
            ),
        ],
    )