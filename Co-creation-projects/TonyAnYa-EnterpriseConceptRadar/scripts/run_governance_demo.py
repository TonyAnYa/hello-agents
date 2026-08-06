"""根据业务影响和反馈生成知识治理任务。"""

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.models import (
    BusinessImpactAssessment,
)
from enterprise_concept_radar.tools import (
    build_governance_task_batch,
    load_feedback_events,
    save_governance_task_batch,
)


def main() -> None:
    """运行知识治理任务生成演示。"""
    impact_path = (
        CONCEPT_CARD_DIR
        / "demo_multi_user_green_power_business_impact.json"
    )
    feedback_path = (
        RUNTIME_DATA_DIR
        / "feedback"
        / "demo_answer_feedback.jsonl"
    )

    if not impact_path.is_file():
        raise SystemExit(
            f"缺少业务影响结果：{impact_path}"
        )

    impact = BusinessImpactAssessment.model_validate_json(
        impact_path.read_text(encoding="utf-8")
    )
    feedback_events = load_feedback_events(
        path=feedback_path,
    )

    batch = build_governance_task_batch(
        impact_assessment=impact,
        feedback_events=feedback_events,
    )

    output_path = save_governance_task_batch(
        batch=batch,
        path=(
            RUNTIME_DATA_DIR
            / "governance"
            / "demo_governance_tasks.json"
        ),
    )

    print("=" * 60)
    print("知识治理任务生成完成")
    print("=" * 60)
    print("概念：", batch.term)
    print("任务数量：", len(batch.tasks))
    print(
        "包含反馈触发任务：",
        batch.generated_from_feedback,
    )

    for task in batch.tasks:
        answer_text = (
            f" | 回答：{task.related_answer_id}"
            if task.related_answer_id
            else ""
        )

        print(
            f"- [{task.priority.value}] "
            f"{task.task_type.value} | "
            f"{task.title}"
            f"{answer_text}"
        )

    print("结果文件：", output_path)


if __name__ == "__main__":
    main()