"""测试历史反馈参与回答排名。"""

import subprocess
import sys

from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerStyle,
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    FeedbackAction,
    FeedbackRating,
    ImpactLevel,
)
from enterprise_concept_radar.scoring import (
    rank_answer_package_with_feedback,
)
from enterprise_concept_radar.tools import (
    create_feedback_event,
)


def build_package() -> AnswerPackage:
    """创建基础指标相同的两份候选回答。"""
    shared_content = (
        "多用户绿电直连可能影响规划建设、调度运行、"
        "市场交易、计量结算、安全责任和知识治理，"
        "建议开展政策核验和跨专业业务评估。"
    )

    return AnswerPackage(
        question="多用户绿电直连有什么影响？",
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        candidates=[
            AnswerCandidate(
                answer_id="answer-a",
                style=AnswerStyle.EXECUTIVE_BRIEF,
                title="回答 A",
                content=shared_content,
                evidence_references=["模拟证据"],
                action_items=["开展政策核验"],
            ),
            AnswerCandidate(
                answer_id="answer-b",
                style=AnswerStyle.PROFESSIONAL_ANALYSIS,
                title="回答 B",
                content=shared_content,
                evidence_references=["模拟证据"],
                action_items=["开展政策核验"],
            ),
        ],
    )


def build_impact() -> BusinessImpactAssessment:
    """创建六领域业务影响评估。"""
    return BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="可能影响多个业务领域。",
        domain_impacts=[
            BusinessDomainImpact(
                domain=domain,
                impact_level=ImpactLevel.MEDIUM,
                impact_summary=f"可能影响{domain.value}。",
            )
            for domain in BusinessDomain
        ],
        confidence=0.8,
    )


def test_no_feedback_uses_neutral_scores() -> None:
    """没有历史反馈时两份回答应使用中性分。"""
    result = rank_answer_package_with_feedback(
        package=build_package(),
        impact_assessment=build_impact(),
        events=[],
    )

    scores = {
        summary.answer_id: summary.user_feedback_score
        for summary in result.feedback_summaries
    }

    assert scores == {
        "answer-a": 50,
        "answer-b": 50,
    }


def test_positive_feedback_changes_ranking() -> None:
    """正向反馈应参与总分并影响推荐顺序。"""
    events = [
        create_feedback_event(
            answer_id="answer-a",
            rating=FeedbackRating.PROFESSIONAL,
        ),
        create_feedback_event(
            answer_id="answer-a",
            action=FeedbackAction.ADOPT,
        ),
        create_feedback_event(
            answer_id="answer-b",
            rating=FeedbackRating.MISMATCH,
        ),
    ]

    result = rank_answer_package_with_feedback(
        package=build_package(),
        impact_assessment=build_impact(),
        events=events,
    )

    feedback_scores = {
        evaluation.answer_id: evaluation.user_feedback_score
        for evaluation in result.ranking.evaluations
    }

    assert feedback_scores["answer-a"] == 100
    assert feedback_scores["answer-b"] == 0
    assert result.ranking.recommended_answer_id == "answer-a"
def test_scoring_package_imports_in_fresh_process() -> None:
    """全新 Python 进程中导入评分包不应发生循环导入。"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from enterprise_concept_radar.scoring "
                "import rank_answer_package_with_feedback; "
                "print('import-ok')"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout