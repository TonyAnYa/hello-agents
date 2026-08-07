"""立即执行一次真实政策追踪任务。"""

from __future__ import annotations

import argparse
from pathlib import Path

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.task_runner import (
    run_tracking_task,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "执行真实政策搜索、抓取、LLM 识别和投递"
        )
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


def main() -> None:
    """执行并打印摘要。"""
    args = build_parser().parse_args()
    execution = run_tracking_task(
        args.task
    )
    run = execution.collection_run

    print("=" * 64)
    print("EnterpriseConceptRadar 在线追踪完成")
    print("=" * 64)
    print("任务：", execution.task.name)
    print("搜索候选：", run.searched_candidate_count)
    print("抓取网页：", run.fetched_page_count)
    print("LLM 调用：", run.llm_call_count)
    print("新增政策：", len(run.documents))
    print("采集异常：", len(run.failures))
    print("输出目录：", execution.output_dir)


if __name__ == "__main__":
    main()
