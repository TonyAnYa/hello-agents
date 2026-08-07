"""从一个真实网页调用大模型提取政策文档。"""

from __future__ import annotations

import argparse
from pathlib import Path

from enterprise_concept_radar.agents.policy_document_extractor_agent import (
    extract_policy_document,
)
from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.services.web_fetcher import (
    fetch_web_page,
)


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description=(
            "下载真实网页并调用大模型判断是否为正式政策"
        )
    )
    parser.add_argument(
        "--url",
        required=True,
        help="真实政策网页 URL",
    )
    parser.add_argument(
        "--source-name",
        default="未指定来源",
        help="政策发布机构提示",
    )
    parser.add_argument(
        "--source-slot",
        type=int,
        default=6,
        choices=range(1, 7),
        help="政策源选项编号，默认 6",
    )
    parser.add_argument(
        "--source-id",
        default="manual-url",
        help="政策源内部标识",
    )
    parser.add_argument(
        "--question",
        default="",
        help="用户关注的问题",
    )
    parser.add_argument(
        "--keyword",
        action="append",
        default=[],
        help="关注关键词，可重复传入",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出 JSON 路径",
    )

    return parser


def main() -> None:
    """执行一次真实网页政策提取。"""
    args = build_parser().parse_args()

    print("正在下载真实网页……")
    page = fetch_web_page(args.url)

    print("正在调用 PolicyDocumentExtractorAgent……")
    document = extract_policy_document(
        page=page,
        source_name_hint=args.source_name,
        source_slot=args.source_slot,
        source_id=args.source_id,
        user_question=args.question,
        keywords=args.keyword,
    )

    if document is None:
        print("结果：该网页未被识别为高置信度正式政策。")
        return

    output_path = (
        args.output
        or (
            RUNTIME_DATA_DIR
            / "online_policies"
            / f"{document.document_id}.json"
        )
    )
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        document.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    print("政策识别成功")
    print("标题：", document.title)
    print("发布机构：", document.source_name)
    print(
        "发布日期：",
        document.published_date.isoformat(),
    )
    print("来源：", document.source_url)
    print("输出：", output_path)


if __name__ == "__main__":
    main()
