"""测试候选回答适配度评分。"""

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerStyle,
)
from enterprise_concept_radar.scoring import (
    calculate_authority_score,
    calculate_keyword_coverage,
    score_answer_candidate,
)


def build_test_candidate() -> AnswerCandidate:
    """创建测试候选回答。"""
    return AnswerCandidate(
        answer_id="answer-a",
        style=AnswerStyle.EXECUTIVE_BRIEF,
        title="管理摘要",
        content=(
            "多用户绿电直连是多个用户协同参与绿电直接供应"
            "的安排，可能影响市场交易、计量结算和安全责任。"
        ),
        evidence_references=[
            "政策原文证据",
            "概念分析结果",
        ],
        action_items=[
            "核验真实政策原文",
            "组织跨专业专题研究",
            "完善知识词条",
        ],
        caveats=[
            "当前来源为教学模拟数据",
        ],
    )


def test_keyword_coverage() -> None:
    """应按照必要关键词计算覆盖率。"""
    score = calculate_keyword_coverage(
        answer=build_test_candidate().content,
        required_keywords=[
            "多用户绿电直连",
            "计量结算",
            "安全责任",
            "调度运行",
        ],
    )

    assert score == 75.0


def test_simulated_source_limits_authority_score() -> None:
    """教学模拟来源的权威依据得分应设置上限。"""
    score = calculate_authority_score(
        evidence_references=[
            "证据一",
            "证据二",
            "证据三",
        ],
        source_is_simulated=True,
    )

    assert score == 55.0


def test_answer_candidate_can_be_scored() -> None:
    """应能生成七项指标和总分。"""
    evaluation = score_answer_candidate(
        question=(
            "多用户绿电直连是什么意思，"
            "对广东电网有什么影响？"
        ),
        term="多用户绿电直连",
        candidate=build_test_candidate(),
        required_keywords=[
            "多用户绿电直连",
            "市场交易",
            "计量结算",
            "安全责任",
        ],
        source_is_simulated=True,
        covered_domain_count=3,
        timeliness_score=80,
        user_feedback_score=50,
    )

    assert evaluation.answer_id == "answer-a"
    assert evaluation.keyword_coverage == 100
    assert evaluation.authority_score == 55
    assert evaluation.business_relevance == 50
    assert evaluation.actionability_score == 75
    assert 0 <= evaluation.total_score <= 100