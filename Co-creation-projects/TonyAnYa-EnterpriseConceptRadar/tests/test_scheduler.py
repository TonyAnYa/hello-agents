"""测试北京时间每日多时间点调度。"""

from datetime import datetime
from zoneinfo import ZoneInfo

from enterprise_concept_radar.scheduler import (
    SchedulerLedger,
    due_schedule_times,
    mark_schedule_triggered,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
)


def build_task() -> TrackingTask:
    """创建默认 08:30、14:00 调度任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些新能源政策？",
        keywords=["新能源"],
    )


def test_morning_schedule_is_due() -> None:
    """北京时间 08:30 应触发上午任务。"""
    now = datetime(
        2026,
        8,
        7,
        8,
        30,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )

    assert due_schedule_times(
        task=build_task(),
        now=now,
        ledger=SchedulerLedger(),
    ) == ["08:30"]


def test_triggered_schedule_does_not_repeat() -> None:
    """同一日期和计划时间只能触发一次。"""
    task = build_task()
    now = datetime(
        2026,
        8,
        7,
        14,
        0,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )
    ledger = mark_schedule_triggered(
        task=task,
        schedule_time="14:00",
        now=now,
        ledger=SchedulerLedger(),
    )

    assert due_schedule_times(
        task=task,
        now=now,
        ledger=ledger,
    ) == []


def test_missed_schedule_outside_window_is_not_due() -> None:
    """超过补跑窗口后不应补执行旧时间点。"""
    now = datetime(
        2026,
        8,
        7,
        12,
        0,
        tzinfo=ZoneInfo("Asia/Shanghai"),
    )

    assert due_schedule_times(
        task=build_task(),
        now=now,
        ledger=SchedulerLedger(),
    ) == []
