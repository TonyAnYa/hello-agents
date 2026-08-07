"""启动跨平台政策追踪调度进程。"""

from __future__ import annotations

import argparse
from pathlib import Path

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.scheduler import (
    run_scheduler_loop,
)


def build_parser() -> argparse.ArgumentParser:
    """创建调度器参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "在用户配置的每日时间点自动运行政策追踪"
        )
    )
    parser.add_argument(
        "--tasks-dir",
        type=Path,
        default=(
            RUNTIME_DATA_DIR
            / "tracking"
            / "tasks"
        ),
        help="追踪任务配置目录",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        help="调度轮询秒数",
    )

    return parser


def main() -> None:
    """持续运行调度器。"""
    args = build_parser().parse_args()

    print("=" * 64)
    print("EnterpriseConceptRadar 调度器已启动")
    print("=" * 64)
    print("任务目录：", args.tasks_dir)
    print("轮询秒数：", args.poll_seconds)
    print("按 Control+C 停止。")

    try:
        run_scheduler_loop(
            tasks_dir=args.tasks_dir,
            poll_seconds=args.poll_seconds,
        )
    except KeyboardInterrupt:
        print()
        print("调度器已停止。")


if __name__ == "__main__":
    main()
