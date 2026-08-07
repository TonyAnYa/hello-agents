"""测试客户推荐配置。"""

from enterprise_concept_radar.customer_setup import (
    apply_recommended_customer_setup,
    build_recommended_task,
)


def test_recommended_task_has_customer_defaults() -> None:
    """推荐任务应包含默认时间、问题和输出目录。"""
    task = build_recommended_task()

    assert task.task_id == (
        "energy-policy-radar"
    )
    assert task.schedule.times == [
        "08:30",
        "14:00",
    ]
    assert "广东电网" in task.question
    assert task.max_concepts_per_policy == 3


def test_customer_setup_creates_sources_and_task(
    tmp_path,
    monkeypatch,
) -> None:
    """推荐设置应生成可读取的来源、任务和报告目录。"""
    source_path = (
        tmp_path
        / "data/runtime/config/"
        "policy_sources.json"
    )
    task_path = (
        tmp_path
        / "data/runtime/tracking/tasks/"
        "energy-policy-radar.json"
    )

    monkeypatch.setattr(
        "enterprise_concept_radar."
        "customer_setup.recommended_source_path",
        lambda: source_path,
    )
    monkeypatch.setattr(
        "enterprise_concept_radar."
        "customer_setup.recommended_task_path",
        lambda: task_path,
    )

    result = (
        apply_recommended_customer_setup(
            output_directory="reports",
            enable_open_web=True,
            project_root=tmp_path,
        )
    )

    assert source_path.is_file()
    assert task_path.is_file()
    assert result.output_directory == (
        tmp_path / "reports"
    ).resolve()
    assert [
        source.slot
        for source
        in result.source_selection.selected_sources()
    ] == [1, 2, 6]
