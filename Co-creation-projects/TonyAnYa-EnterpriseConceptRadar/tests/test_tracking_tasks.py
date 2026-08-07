"""测试用户追踪任务配置。"""

import pytest

from enterprise_concept_radar.tracking_tasks import (
    DEFAULT_OUTPUT_DIRECTORY,
    TrackingSchedule,
    TrackingTask,
    load_tracking_task,
    save_tracking_task,
)


def build_task() -> TrackingTask:
    """创建最小有效任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些新能源政策？",
        keywords=[
            "新能源",
            "电力市场",
        ],
    )


def test_default_schedule_uses_beijing_times() -> None:
    """默认使用北京时间 08:30 和 14:00。"""
    task = build_task()

    assert task.schedule.timezone == (
        "Asia/Shanghai"
    )
    assert task.schedule.times == [
        "08:30",
        "14:00",
    ]


def test_default_output_directory_is_portable() -> None:
    """默认输出路径应能在 macOS 和 Windows 展开。"""
    assert build_task().output_directory == (
        DEFAULT_OUTPUT_DIRECTORY
    )
    assert DEFAULT_OUTPUT_DIRECTORY.startswith(
        "~/"
    )


def test_schedule_times_are_sorted_and_unique() -> None:
    """用户时间应去重并排序。"""
    schedule = TrackingSchedule(
        times=[
            "14:00",
            "08:30",
            "14:00",
        ]
    )

    assert schedule.times == [
        "08:30",
        "14:00",
    ]


def test_invalid_schedule_time_is_rejected() -> None:
    """不合法时间格式应被拒绝。"""
    with pytest.raises(
        ValueError,
        match="HH:MM",
    ):
        TrackingSchedule(
            times=["25:00"]
        )


def test_tracking_task_round_trip(
    tmp_path,
) -> None:
    """任务保存后应能恢复。"""
    task = build_task()
    path = save_tracking_task(
        task,
        tmp_path / "task.json",
    )
    restored = load_tracking_task(path)

    assert restored == task


def test_intelligence_limits_have_safe_defaults() -> None:
    """默认限制应控制单次 LLM 分析规模。"""
    task = build_task()

    assert task.max_concepts_per_policy == 3
    assert task.max_intelligence_items_per_run == 6
    assert task.minimum_concept_confidence == 0.65
    assert task.minimum_novelty_score == 50

