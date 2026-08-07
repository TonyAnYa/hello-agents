"""使用 Y/N 和时间输入修改每日定时输出。"""

from __future__ import annotations

from pathlib import Path

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.schedule_settings import (
    DEFAULT_SCHEDULE_TIMES,
    ScheduleConfigurationError,
    parse_schedule_times,
    save_task_schedule,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTaskError,
    load_tracking_task,
)

DEFAULT_TASK_PATH = (
    RUNTIME_DATA_DIR
    / "tracking"
    / "tasks"
    / "energy-policy-radar.json"
)


def ask_yes_no(
    prompt: str,
    *,
    default: bool,
) -> bool:
    """只接受 Y/N。"""
    suffix = (
        "[Y/n]"
        if default
        else "[y/N]"
    )

    while True:
        value = input(
            f"{prompt}{suffix} "
        ).strip().casefold()

        if not value:
            return default

        if value in {
            "y",
            "yes",
        }:
            return True

        if value in {
            "n",
            "no",
        }:
            return False

        print("请输入 Y 或 N。")


def ask_schedule_times(
    current_times: list[str],
) -> list[str]:
    """让客户输入一个或多个每日时间。"""
    current_text = "、".join(
        current_times
    )

    while True:
        value = input(
            "请输入每日输出时间，"
            "多个时间使用逗号分隔"
            f"（当前：{current_text}）："
        ).strip()

        if not value:
            return list(current_times)

        try:
            times = (
                parse_schedule_times(
                    value
                )
            )
        except ScheduleConfigurationError as exc:
            print(
                f"时间格式不正确：{exc}"
            )
            continue

        print(
            "新的定时输出时间：",
            "、".join(times),
        )

        if ask_yes_no(
            "确认使用这些时间吗？",
            default=True,
        ):
            return times


def configure_schedule(
    task_path: Path = DEFAULT_TASK_PATH,
) -> None:
    """修改指定任务的定时输出。"""
    try:
        task = load_tracking_task(
            task_path
        )
    except TrackingTaskError as exc:
        raise SystemExit(
            f"无法读取追踪任务：{exc}"
        ) from exc

    print("=" * 68)
    print("EnterpriseConceptRadar 定时输出设置")
    print("=" * 68)
    print("任务：", task.name)
    print(
        "当前状态：",
        (
            "已启用"
            if task.schedule.enabled
            else "已关闭"
        ),
    )
    print(
        "当前时间：",
        "、".join(
            task.schedule.times
        ),
        task.schedule.timezone,
    )
    print()
    print(
        "“立即输出”不受这里的时间限制，"
        "选择后会马上执行。"
    )
    print()

    enabled = ask_yes_no(
        "启用每天定时输出吗？",
        default=(
            task.schedule.enabled
        ),
    )

    if not enabled:
        updated = save_task_schedule(
            task_path=task_path,
            enabled=False,
        )
        print()
        print("定时输出已关闭。")
        print(
            "仍可随时在运行菜单中"
            "选择“立即输出”。"
        )
        print(
            "保留的时间：",
            "、".join(
                updated.schedule.times
            ),
        )
        return

    current_times = list(
        task.schedule.times
    )

    if ask_yes_no(
        "保留当前定时输出时间吗？",
        default=True,
    ):
        times = current_times
    elif ask_yes_no(
        "恢复推荐时间 08:30、14:00 吗？",
        default=True,
    ):
        times = list(
            DEFAULT_SCHEDULE_TIMES
        )
    else:
        times = ask_schedule_times(
            current_times
        )

    updated = save_task_schedule(
        task_path=task_path,
        enabled=True,
        times=times,
    )

    print()
    print("定时输出设置已保存。")
    print(
        "每日时间：",
        "、".join(
            updated.schedule.times
        ),
        updated.schedule.timezone,
    )


def main() -> None:
    """命令行入口。"""
    configure_schedule()


if __name__ == "__main__":
    main()
