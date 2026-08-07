"""立即执行一次真实政策追踪与完整智能分析任务。"""

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
            "执行真实政策搜索、抓取、概念发现、"
            "智能分析、评分、治理任务和投递"
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
    """执行并打印完整运行摘要。"""
    args = build_parser().parse_args()
    execution = run_tracking_task(
        args.task
    )
    collection = execution.collection_run
    intelligence = execution.intelligence_run

    print("=" * 64)
    print("EnterpriseConceptRadar 在线追踪完成")
    print("=" * 64)
    print("任务：", execution.task.name)
    print(
        "搜索候选：",
        collection.searched_candidate_count,
    )
    print(
        "抓取网页：",
        collection.fetched_page_count,
    )
    print(
        "正式政策：",
        len(collection.documents),
    )
    print(
        "完整概念情报项：",
        len(intelligence.intelligence_items),
    )
    print(
        "LLM 分析阶段：",
        intelligence.llm_stage_count,
    )
    print(
        "采集异常：",
        len(collection.failures),
    )
    print(
        "分析异常：",
        len(intelligence.failures),
    )
    print("输出目录：", execution.output_dir)
    print("最近结果：", execution.latest_dir)


if __name__ == "__main__":
    main()
