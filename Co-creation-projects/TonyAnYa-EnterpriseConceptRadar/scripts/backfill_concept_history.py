"""从已有真实报告回填本地概念历史，不联网。"""

import argparse
from datetime import date, datetime
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.concept_history import (
    concept_history_path,
    load_concept_history,
    record_intelligence_history,
)


class BackfillPolicyDocument(BaseModel):
    """回填只需要政策 ID 和发布日期。"""

    model_config = ConfigDict(
        extra="ignore",
    )

    document_id: str = Field(
        min_length=1,
    )
    published_date: date


class BackfillCollectionRun(BaseModel):
    """兼容历史版本的最小采集运行结构。"""

    model_config = ConfigDict(
        extra="ignore",
    )

    documents: list[
        BackfillPolicyDocument
    ] = Field(
        default_factory=list,
    )


class BackfillConceptCandidate(BaseModel):
    """回填只需要概念名称和发现时间。"""

    model_config = ConfigDict(
        extra="ignore",
    )

    term: str = Field(
        min_length=1,
    )
    detected_at: datetime


class BackfillIntelligenceItem(BaseModel):
    """兼容历史版本的最小概念情报结构。"""

    model_config = ConfigDict(
        extra="ignore",
    )

    document_id: str = Field(
        min_length=1,
    )
    policy_title: str = Field(
        min_length=1,
    )
    policy_source_name: str = Field(
        min_length=1,
    )
    policy_source_url: str = Field(
        min_length=1,
    )
    candidate: BackfillConceptCandidate


class BackfillIntelligenceRun(BaseModel):
    """兼容历史版本的最小智能运行结构。"""

    model_config = ConfigDict(
        extra="ignore",
    )

    intelligence_items: list[
        BackfillIntelligenceItem
    ] = Field(
        default_factory=list,
    )


def parse_collection_run(
    path: Path,
) -> BackfillCollectionRun:
    """只校验概念历史回填需要的采集字段。"""
    return (
        BackfillCollectionRun
        .model_validate_json(
            path.read_text(
                encoding="utf-8",
            )
        )
    )


def parse_intelligence_run(
    path: Path,
) -> BackfillIntelligenceRun:
    """忽略历史报告中的输出型/新增字段。"""
    return (
        BackfillIntelligenceRun
        .model_validate_json(
            path.read_text(
                encoding="utf-8",
            )
        )
    )


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "扫描已有真实运行结果并重建概念历史；"
            "本命令不访问网络、不调用大模型"
        )
    )
    parser.add_argument(
        "--task-id",
        default="energy-policy-radar",
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=(
            Path.home()
            / "Documents"
            / "EnterpriseConceptRadarReports"
        ),
    )
    return parser


def main() -> None:
    """执行幂等回填。"""
    args = build_parser().parse_args()
    task_root = (
        args.reports_root
        / args.task_id
    )

    if not task_root.is_dir():
        raise SystemExit(
            f"报告目录不存在：{task_root}"
        )

    run_dirs: set[Path] = set()

    for intelligence_path in task_root.rglob(
        "intelligence_run.json"
    ):
        run_dir = intelligence_path.parent
        collection_path = (
            run_dir
            / "collection_run.json"
        )

        if collection_path.is_file():
            run_dirs.add(run_dir)

    processed = 0
    skipped = 0

    for run_dir in sorted(run_dirs):
        collection_path = (
            run_dir
            / "collection_run.json"
        )
        intelligence_path = (
            run_dir
            / "intelligence_run.json"
        )

        try:
            collection = (
                parse_collection_run(
                    collection_path
                )
            )
            intelligence = (
                parse_intelligence_run(
                    intelligence_path
                )
            )
        except Exception as exc:
            skipped += 1
            print(
                "[跳过]",
                run_dir,
                "；",
                f"{type(exc).__name__}: {exc}",
            )
            continue

        record_intelligence_history(
            task_id=args.task_id,
            collection_run=collection,
            intelligence_run=intelligence,
        )
        processed += 1

    store = load_concept_history(
        task_id=args.task_id
    )
    output = concept_history_path(
        args.task_id
    )

    print("=" * 64)
    print(
        "EnterpriseConceptRadar "
        "概念历史回填完成"
    )
    print("=" * 64)
    print(
        "成功扫描运行目录：",
        processed,
    )
    print(
        "跳过不兼容/损坏目录：",
        skipped,
    )
    print(
        "历史概念数：",
        len(store.entries),
    )
    print(
        "历史文件：",
        output,
    )
    print("联网：否")
    print("LLM 调用：0")

    for entry in store.entries:
        print(
            "-",
            entry.canonical_term,
            "| 最早：",
            entry.first_seen_date,
            "| 最近：",
            entry.last_seen_date,
            "| 政策次数：",
            len(entry.occurrences),
        )


if __name__ == "__main__":
    main()
