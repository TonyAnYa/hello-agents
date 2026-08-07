"""测试客户定时输出设置。"""

import pytest

from enterprise_concept_radar.customer_setup import (
    build_recommended_task,
)
from enterprise_concept_radar.schedule_settings import (
    ScheduleConfigurationError,
    parse_schedule_times,
    update_task_schedule,
)


def test_parse_schedule_times_sorts_and_deduplicates() -> None:
    """多个时间应校验、去重并排序。"""
    assert parse_schedule_times(
        "17:30，09:00,17:30"
    ) == [
        "09:00",
        "17:30",
    ]


def test_parse_schedule_times_rejects_invalid_value() -> None:
    """非法小时分钟必须拒绝。"""
    with pytest.raises(
        ScheduleConfigurationError,
        match="HH:MM",
    ):
        parse_schedule_times(
            "25:90"
        )


def test_schedule_can_be_disabled_without_losing_times() -> None:
    """关闭定时后应保留时间，方便重新启用。"""
    task = build_recommended_task(
        schedule_times=[
            "09:00",
            "17:30",
        ]
    )
    updated = update_task_schedule(
        task=task,
        enabled=False,
    )

    assert (
        updated.schedule.enabled
        is False
    )
    assert updated.schedule.times == [
        "09:00",
        "17:30",
    ]


def test_recommended_task_accepts_custom_schedule() -> None:
    """首次客户设置可直接写入自定义时间。"""
    task = build_recommended_task(
        schedule_enabled=True,
        schedule_times=[
            "07:45",
            "18:15",
        ],
    )

    assert (
        task.schedule.enabled
        is True
    )
    assert task.schedule.times == [
        "07:45",
        "18:15",
    ]
