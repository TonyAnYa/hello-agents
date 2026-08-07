"""不联网显示追踪任务、运行状态和最近结果。"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.feedback_workflow import (
    latest_intelligence_path,
)
from enterprise_concept_radar.output_paths import (
    resolve_output_directory,
)
from enterprise_concept_radar.task_runner import (
    tracking_state_path,
)
from enterprise_concept_radar.tracking_tasks import (
    load_tracking_state,
    load_tracking_task,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description="显示政策追踪任务当前状态"
    )
    parser.add_argument(
        "--task",
        type=Path,
        default=(
            RUNTIME_DATA_DIR
            / "tracking"
            / "tasks"
            / "energy-policy-radar.json"
        ),
        help="追踪任务 JSON 文件",
    )

    return parser


def next_schedule_text(
    *,
    timezone_name: str,
    times: list[str],
) -> str:
    """根据当前时间显示今天剩余或明天首个计划点。"""
    timezone_info = ZoneInfo(
        timezone_name
    )
    now = datetime.now(timezone_info)
    today_remaining = [
        value
        for value in times
        if value > now.strftime("%H:%M")
    ]

    if today_remaining:
        return (
            f"今天 {today_remaining[0]} "
            f"({timezone_name})"
        )

    return (
        f"明天 {times[0]} "
        f"({timezone_name})"
    )


def main() -> None:
    """打印不需要联网的运行状态。"""
    args = build_parser().parse_args()
    task = load_tracking_task(args.task)
    state = load_tracking_state(
        tracking_state_path(task.task_id),
        task_id=task.task_id,
    )
    output_root = resolve_output_directory(
        task.output_directory
    )
    latest_path = latest_intelligence_path(
        task=task
    )

    print("=" * 64)
    print("EnterpriseConceptRadar 当前状态")
    print("=" * 64)
    print("任务：", task.name)
    print("任务 ID：", task.task_id)
    print(
        "调度：",
        "、".join(task.schedule.times),
        task.schedule.timezone,
    )
    print(
        "下一计划时间：",
        next_schedule_text(
            timezone_name=(
                task.schedule.timezone
            ),
            times=task.schedule.times,
        ),
    )
    print("输出根目录：", output_root)
    print(
        "最近智能结果：",
        (
            latest_path
            if latest_path.is_file()
            else "尚未生成"
        ),
    )
    print(
        "最近开始：",
        state.last_started_at or "尚未运行",
    )
    print(
        "最近成功：",
        state.last_successful_at or "尚未成功运行",
    )
    print("失败次数：", state.failed_runs)
    print(
        "最近错误：",
        state.last_error or "无",
    )


if __name__ == "__main__":
    main()
