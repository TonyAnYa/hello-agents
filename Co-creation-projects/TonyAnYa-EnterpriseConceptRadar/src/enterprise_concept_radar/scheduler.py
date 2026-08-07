"""跨平台、无额外依赖的每日多时间点任务调度器。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.task_runner import (
    run_tracking_task,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
    load_tracking_task,
)


class SchedulerError(RuntimeError):
    """调度账本或任务目录无效。"""


class SchedulerLedger(BaseModel):
    """防止同一任务在同一日期和时间点重复运行。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    triggered_dates: dict[str, date] = Field(
        default_factory=dict,
        description="task_id|HH:MM 对应最近触发日期",
    )


def scheduler_ledger_path() -> Path:
    """返回默认调度账本路径。"""
    return (
        RUNTIME_DATA_DIR
        / "tracking"
        / "scheduler_ledger.json"
    )


def load_scheduler_ledger(
    path: str | Path | None = None,
) -> SchedulerLedger:
    """读取调度账本；不存在时返回空账本。"""
    active_path = (
        Path(path)
        if path is not None
        else scheduler_ledger_path()
    )

    if not active_path.exists():
        return SchedulerLedger()

    try:
        return SchedulerLedger.model_validate_json(
            active_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        ValidationError,
    ) as exc:
        raise SchedulerError(
            f"调度账本无效：{active_path}；{exc}"
        ) from exc


def save_scheduler_ledger(
    ledger: SchedulerLedger,
    path: str | Path | None = None,
) -> Path:
    """保存调度账本。"""
    active_path = (
        Path(path)
        if path is not None
        else scheduler_ledger_path()
    )
    active_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    active_path.write_text(
        ledger.model_dump_json(
            indent=2,
        ),
        encoding="utf-8",
    )

    return active_path


def due_schedule_times(
    *,
    task: TrackingTask,
    now: datetime,
    ledger: SchedulerLedger,
) -> list[str]:
    """返回当前应触发且今日尚未运行的时间点。"""
    if not task.schedule.enabled:
        return []

    local_now = now.astimezone(
        ZoneInfo(task.schedule.timezone)
    )
    due: list[str] = []

    for schedule_time in task.schedule.times:
        hour_text, minute_text = (
            schedule_time.split(":", 1)
        )
        target = local_now.replace(
            hour=int(hour_text),
            minute=int(minute_text),
            second=0,
            microsecond=0,
        )
        late_by = local_now - target

        if late_by < timedelta(0):
            continue

        if late_by > timedelta(
            minutes=(
                task.schedule.catch_up_minutes
            )
        ):
            continue

        ledger_key = (
            f"{task.task_id}|{schedule_time}"
        )

        if (
            ledger.triggered_dates.get(ledger_key)
            == local_now.date()
        ):
            continue

        due.append(schedule_time)

    return due


def mark_schedule_triggered(
    *,
    task: TrackingTask,
    schedule_time: str,
    now: datetime,
    ledger: SchedulerLedger,
) -> SchedulerLedger:
    """在运行前记录触发，防止短轮询重复调用 LLM。"""
    local_date = now.astimezone(
        ZoneInfo(task.schedule.timezone)
    ).date()
    updated = dict(ledger.triggered_dates)
    updated[
        f"{task.task_id}|{schedule_time}"
    ] = local_date

    return ledger.model_copy(
        update={
            "triggered_dates": updated,
        }
    )


def discover_tracking_tasks(
    tasks_dir: str | Path,
) -> list[Path]:
    """按照文件名顺序发现任务配置。"""
    directory = Path(tasks_dir)

    if not directory.is_dir():
        raise SchedulerError(
            f"任务目录不存在：{directory}"
        )

    return sorted(
        directory.glob("*.json")
    )


def run_scheduler_loop(
    *,
    tasks_dir: str | Path,
    poll_seconds: int = 30,
    run_func: Callable[..., object] = (
        run_tracking_task
    ),
    ledger_path: str | Path | None = None,
    max_cycles: int | None = None,
) -> None:
    """持续检查任务并在用户配置的时间点执行。

    max_cycles 仅用于测试或临时演示；正式运行时保持 None。
    """
    if poll_seconds <= 0:
        raise SchedulerError(
            "poll_seconds 必须大于 0"
        )

    cycles = 0

    while True:
        now = datetime.now().astimezone()
        ledger = load_scheduler_ledger(
            ledger_path
        )

        for task_path in discover_tracking_tasks(
            tasks_dir
        ):
            try:
                task = load_tracking_task(
                    task_path
                )
            except Exception as exc:
                print(
                    f"[配置错误] {task_path.name}: "
                    f"{type(exc).__name__}: {exc}"
                )
                continue

            for schedule_time in due_schedule_times(
                task=task,
                now=now,
                ledger=ledger,
            ):
                ledger = mark_schedule_triggered(
                    task=task,
                    schedule_time=schedule_time,
                    now=now,
                    ledger=ledger,
                )
                save_scheduler_ledger(
                    ledger,
                    ledger_path,
                )

                print(
                    f"[{now.isoformat()}] "
                    f"执行任务 {task.task_id} "
                    f"（计划时间 {schedule_time}）"
                )

                try:
                    execution = run_func(
                        task_path
                    )
                    output_dir = getattr(
                        execution,
                        "output_dir",
                        "",
                    )
                    print(
                        "[完成] 输出目录："
                        f"{output_dir}"
                    )
                except Exception as exc:
                    print(
                        f"[失败] {task.task_id}: "
                        f"{type(exc).__name__}: {exc}"
                    )

        cycles += 1

        if (
            max_cycles is not None
            and cycles >= max_cycles
        ):
            return

        time.sleep(poll_seconds)
