"""EnterpriseConceptRadar 命令行入口。"""

from __future__ import annotations

import argparse
import platform
import sys

from enterprise_concept_radar import __version__
from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    DATA_DIR,
    PROJECT_ROOT,
    REPORT_DIR,
    ensure_runtime_directories,
)
from enterprise_concept_radar.workflow import (
    run_demo_concept_discovery,
)


def show_environment() -> None:
    """打印当前开发环境和项目路径。"""
    ensure_runtime_directories()

    print("=" * 60)
    print("EnterpriseConceptRadar 环境检查")
    print("=" * 60)
    print(f"项目版本：{__version__}")
    print(f"Python：{sys.version.split()[0]}")
    print(f"操作系统：{platform.system()} {platform.release()}")
    print(f"项目根目录：{PROJECT_ROOT}")
    print(f"数据目录：{DATA_DIR}")
    print(f"报告目录：{REPORT_DIR}")
    print(f"概念卡片目录：{CONCEPT_CARD_DIR}")
    print("=" * 60)
    print("基础环境检查完成")


def run_demo_discovery_command() -> None:
    """运行概念发现演示并打印摘要。"""
    result = run_demo_concept_discovery()

    print("=" * 60)
    print("EnterpriseConceptRadar 概念发现演示")
    print("=" * 60)
    print(f"政策标题：{result.document.title}")
    print(f"候选数量：{len(result.candidates)}")
    print()

    for candidate in result.candidates:
        print(
            f"- {candidate.term} | "
            f"{candidate.candidate_type.value} | "
            f"新颖度 {candidate.novelty_score}"
        )

    print()
    print(f"报告已保存：{result.report_path}")
    print("=" * 60)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="concept-radar",
        description=(
            "能源政策新词新概念追踪与知识治理智能体"
        ),
    )
    subparsers = parser.add_subparsers(
        dest="command"
    )

    subparsers.add_parser(
        "env",
        help="显示项目环境信息",
    )
    subparsers.add_parser(
        "demo-discovery",
        help="运行本地教学政策概念发现演示",
    )

    return parser


def main() -> None:
    """命令行主函数。"""
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {
        None,
        "env",
    }:
        show_environment()
        return

    if args.command == "demo-discovery":
        run_demo_discovery_command()
        return

    parser.error(
        f"不支持的命令：{args.command}"
    )


if __name__ == "__main__":
    main()