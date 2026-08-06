"""测试知识治理任务数据模型。"""

import pytest
from pydantic import ValidationError

from enterprise_concept_radar.models import (
    GovernanceTask,
    GovernanceTaskBatch,
    GovernanceTaskPriority,
    GovernanceTaskType,
)


def build_task(
    task_id: str = "task-a",
    term: str = "测试概念",
) -> GovernanceTask:
    """创建测试治理任务。"""
    return GovernanceTask(
        task_id=task_id,
        term=term,
        source_document_id="demo-1",
        task_type=GovernanceTaskType.CONCEPT_ENTRY,
        priority=GovernanceTaskPriority.MEDIUM,
        title="建立概念词条",
        description="建立概念词条并补充来源信息。",
        trigger="业务影响分析建议",
    )


def test_governance_task_batch_can_be_created() -> None:
    """合法任务批次应通过校验。"""
    batch = GovernanceTaskBatch(
        term="测试概念",
        source_document_id="demo-1",
        tasks=[
            build_task(),
        ],
    )

    assert len(batch.tasks) == 1


def test_duplicate_task_ids_are_rejected() -> None:
    """同一批次中的任务 ID 不能重复。"""
    task = build_task()

    with pytest.raises(
        ValidationError,
        match="task_id 不能重复",
    ):
        GovernanceTaskBatch(
            term="测试概念",
            source_document_id="demo-1",
            tasks=[
                task,
                task,
            ],
        )


def test_task_term_must_match_batch() -> None:
    """任务概念与批次概念不一致时应拒绝。"""
    with pytest.raises(
        ValidationError,
        match="term 不一致",
    ):
        GovernanceTaskBatch(
            term="测试概念",
            source_document_id="demo-1",
            tasks=[
                build_task(
                    term="另一个概念",
                ),
            ],
        )