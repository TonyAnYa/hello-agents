"""面向客户的定时输出设置。"""

from __future__ import annotations

import re
from pathlib import Path

from enterprise_concept_radar.tracking_tasks import (
    TrackingSchedule,
    TrackingTask,
    TrackingTaskError,
    load_tracking_task,
    save_tracking_task,
)

TIME_PATTERN = re.compile(
    r"^(?:[01]\d|2[0-3]):[0-5]\d$"
)
DEFAULT_SCHEDULE_TIMES = (
    "08:30",
    "14:00",
)


class ScheduleConfigurationError(
    RuntimeError
):
    """定时输出配置无效。"""


def parse_schedule_times(
    raw_value: str,
) -> list[str]:
    """解析一个或多个 HH:MM 时间。"""
    values = [
        item.strip()
        for item in (
            raw_value
            .replace("，", ",")
            .replace("、", ",")
            .split(",")
        )
        if item.strip()
    ]

    if not values:
        raise ScheduleConfigurationError(
            "至少需要填写一个输出时间"
        )

    normalized: list[str] = []

    for value in values:
        if not TIME_PATTERN.fullmatch(
            value
        ):
            raise ScheduleConfigurationError(
                "时间必须使用 HH:MM 格式，"
                "例如 08:30 或 14:00"
            )

        if value not in normalized:
            normalized.append(value)

    return sorted(normalized)


def update_task_schedule(
    *,
    task: TrackingTask,
    enabled: bool,
    times: list[str] | None = None,
) -> TrackingTask:
    """更新任务定时设置，不改变其他任务参数。"""
    active_times = (
        list(times)
        if times is not None
        else list(task.schedule.times)
    )

    if not active_times:
        active_times = list(
            DEFAULT_SCHEDULE_TIMES
        )

    schedule = TrackingSchedule(
        enabled=enabled,
        timezone=task.schedule.timezone,
        times=active_times,
        catch_up_minutes=(
            task.schedule.catch_up_minutes
        ),
    )

    return task.model_copy(
        update={
            "schedule": schedule,
        }
    )


def save_task_schedule(
    *,
    task_path: str | Path,
    enabled: bool,
    times: list[str] | None = None,
) -> TrackingTask:
    """读取、更新并保存一个任务的定时设置。"""
    path = Path(task_path)

    try:
        task = load_tracking_task(
            path
        )
    except TrackingTaskError as exc:
        raise ScheduleConfigurationError(
            str(exc)
        ) from exc

    updated = update_task_schedule(
        task=task,
        enabled=enabled,
        times=times,
    )
    save_tracking_task(
        updated,
        path,
    )

    return updated
