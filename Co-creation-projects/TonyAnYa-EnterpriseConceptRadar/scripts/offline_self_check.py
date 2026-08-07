"""运行不访问网络的安装和配置自检。"""

from __future__ import annotations

import argparse

from enterprise_concept_radar.diagnostics import (
    run_offline_diagnostics,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "检查 Python、依赖、提示词、任务、"
            "来源和输出目录，不访问网络"
        )
    )
    parser.add_argument(
        "--require-runtime",
        action="store_true",
        help="把尚未填写的正式运行配置视为失败",
    )

    return parser


def main() -> None:
    """打印离线自检结果并设置退出状态。"""
    args = build_parser().parse_args()
    report = run_offline_diagnostics(
        require_runtime=args.require_runtime
    )

    print("=" * 68)
    print("EnterpriseConceptRadar 离线自检")
    print("=" * 68)

    for check in report.checks:
        print(
            f"[{check.status}] "
            f"{check.name}：{check.message}"
        )

    print("-" * 68)
    print("失败：", report.failure_count)
    print("警告：", report.warning_count)
    print(
        "结果：",
        (
            "通过"
            if report.passed
            else "未通过"
        ),
    )
    print(
        "说明：本命令未访问网络，"
        "未调用 SerpAPI 或大模型。"
    )

    if not report.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
