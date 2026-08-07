"""生成不包含密钥和本地运行数据的最终发行 ZIP。"""

from __future__ import annotations

import argparse
from pathlib import Path

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
)
from enterprise_concept_radar.release import (
    PROJECT_VERSION,
    build_release_archive,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "构建可在 macOS 和 Windows 使用的"
            "干净 EnterpriseConceptRadar 压缩包"
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "dist",
        help="发行压缩包保存目录",
    )
    parser.add_argument(
        "--version",
        default=PROJECT_VERSION,
        help="发行版本号",
    )

    return parser


def main() -> None:
    """构建并打印发行包校验信息。"""
    args = build_parser().parse_args()
    result = build_release_archive(
        project_root=PROJECT_ROOT,
        destination_directory=args.output_dir,
        version=args.version,
    )

    print("=" * 68)
    print("EnterpriseConceptRadar 发行包生成完成")
    print("=" * 68)
    print("文件：", result.archive_path)
    print("顶层目录：", result.release_root_name)
    print("文件数量：", result.file_count)
    print(
        "来源提交：",
        result.source_commit or "未检测到",
    )
    print(
        "ZIP SHA-256：",
        result.archive_sha256,
    )
    print()
    print(
        "已排除 .env、虚拟环境、data/runtime、"
        "用户简报、缓存和 Git 元数据。"
    )


if __name__ == "__main__":
    main()
