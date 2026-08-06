"""测试知识治理任务生成工具。"""
import pytest

from enterprise_concept_radar.models import (
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    FeedbackAction,
    FeedbackRating,
    GovernanceTaskPriority,
    GovernanceTaskType,
    ImpactLevel,
)
from enterprise_concept_radar.tools import (
    build_governance_task_batch,
    create_feedback_event,
    infer_governance_task_type,
    load_governance_task_batch,
    save_governance_task_batch,
)


def build_impact() -> BusinessImpactAssessment:
    """创建测试业务影响评估。"""
    return BusinessImpactAssessment(
        term="多用户绿电直连",
        source_document_id="demo-policy-2026-001",
        source_is_simulated=True,
        overall_summary="可能影响多个电网业务领域。",
        domain_impacts=[
            BusinessDomainImpact(
                domain=domain,
                impact_level=ImpactLevel.MEDIUM,
                impact_summary=f"可能影响{domain.value}。",
            )
            for domain in BusinessDomain
        ],
        governance_tasks=[
            "建立多用户绿电直连概念词条",
            "建立概念与业务规则的映射关系",
        ],
        uncertainties=[
            "当前来源为教学模拟数据。",
        ],
        confidence=0.8,
    )


def test_impact_creates_governance_tasks() -> None:
    """业务影响建议和不确定事项应生成治理任务。"""
    batch = build_governance_task_batch(
        impact_assessment=build_impact(),
    )

    task_types = {
        task.task_type
        for task in batch.tasks
    }

    assert GovernanceTaskType.CONCEPT_ENTRY in task_types
    assert (
        GovernanceTaskType.BUSINESS_RULE_MAPPING
        in task_types
    )
    assert (
        GovernanceTaskType.SOURCE_VERIFICATION
        in task_types
    )


def test_feedback_creates_review_and_standard_qa_tasks() -> None:
    """不匹配和采纳反馈应触发相应治理任务。"""
    events = [
        create_feedback_event(
            answer_id="answer-a",
            rating=FeedbackRating.MISMATCH,
        ),
        create_feedback_event(
            answer_id="answer-a",
            action=FeedbackAction.ADOPT,
        ),
    ]

    batch = build_governance_task_batch(
        impact_assessment=build_impact(),
        feedback_events=events,
    )

    related_tasks = [
        task
        for task in batch.tasks
        if task.related_answer_id == "answer-a"
    ]
    task_types = {
        task.task_type
        for task in related_tasks
    }

    assert GovernanceTaskType.ANSWER_REVIEW in task_types
    assert GovernanceTaskType.STANDARD_QA in task_types
    assert any(
        task.priority == GovernanceTaskPriority.HIGH
        for task in related_tasks
        if task.task_type
        == GovernanceTaskType.ANSWER_REVIEW
    )
    assert batch.generated_from_feedback is True


def test_governance_tasks_can_round_trip_json(
    tmp_path,
) -> None:
    """治理任务批次应能保存并重新读取。"""
    path = tmp_path / "governance_tasks.json"
    batch = build_governance_task_batch(
        impact_assessment=build_impact(),
    )

    save_governance_task_batch(
        batch=batch,
        path=path,
    )
    restored = load_governance_task_batch(
        path=path,
    )

    assert restored.term == batch.term
    assert len(restored.tasks) == len(batch.tasks)
@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        (
            "建立多用户绿电直连概念的知识条目",
            GovernanceTaskType.CONCEPT_ENTRY,
        ),
        (
            "核验政策原文、发布机构和文号",
            GovernanceTaskType.SOURCE_VERIFICATION,
        ),
        (
            "复核回答 answer-a 的证据引用",
            GovernanceTaskType.ANSWER_REVIEW,
        ),
        (
            "将优质内容沉淀为标准问答",
            GovernanceTaskType.STANDARD_QA,
        ),
        (
            "组织跨部门研讨会并建立业务流程映射关系",
            GovernanceTaskType.BUSINESS_RULE_MAPPING,
        ),
    ],
)
def test_governance_task_type_can_be_inferred(
    text: str,
    expected_type: GovernanceTaskType,
) -> None:
    """五类知识治理任务应按明确关键词分类。"""
    assert (
        infer_governance_task_type(text)
        == expected_type
    )