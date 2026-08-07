"""对最近一次智能简报中的候选回答记录反馈。"""

from __future__ import annotations

import argparse
from pathlib import Path

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.feedback_workflow import (
    build_feedback_options,
    load_latest_intelligence_run,
    record_feedback_for_option,
)
from enterprise_concept_radar.models import (
    FeedbackAction,
    FeedbackRating,
)
from enterprise_concept_radar.tracking_tasks import (
    load_tracking_task,
)

RATING_OPTIONS = {
    "0": None,
    "1": FeedbackRating.PROFESSIONAL,
    "2": FeedbackRating.AVERAGE,
    "3": FeedbackRating.MISMATCH,
}
ACTION_OPTIONS = {
    "0": None,
    "1": FeedbackAction.ADOPT,
    "2": FeedbackAction.COPY,
}


def build_parser() -> argparse.ArgumentParser:
    """创建命令行参数。"""
    parser = argparse.ArgumentParser(
        description="评价最近一次智能简报中的回答"
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
    parser.add_argument(
        "--feedback-file",
        type=Path,
        default=None,
        help="自定义反馈 JSONL 文件",
    )

    return parser


def choose_index(
    *,
    count: int,
) -> int:
    """读取合法的回答序号。"""
    while True:
        raw_value = input(
            f"请选择回答序号（1-{count}）："
        ).strip()

        try:
            index = int(raw_value)
        except ValueError:
            print("请输入数字。")
            continue

        if 1 <= index <= count:
            return index - 1

        print("序号超出范围。")


def choose_mapping(
    *,
    prompt: str,
    mapping: dict[str, object],
) -> object:
    """从固定选项中读取一个值。"""
    while True:
        value = input(prompt).strip()

        if value in mapping:
            return mapping[value]

        print(
            "无效选项，可选："
            + "、".join(mapping)
        )


def main() -> None:
    """交互式记录反馈。"""
    args = build_parser().parse_args()
    task = load_tracking_task(args.task)
    run = load_latest_intelligence_run(
        task=task
    )
    options = build_feedback_options(run)

    if not options:
        raise SystemExit(
            "最近一次结果中没有可评价的候选回答。"
        )

    print("=" * 64)
    print("EnterpriseConceptRadar 回答反馈")
    print("=" * 64)

    for index, option in enumerate(
        options,
        start=1,
    ):
        recommended_text = (
            " [当前推荐]"
            if option.recommended
            else ""
        )
        print()
        print(
            f"{index}. {option.term} / "
            f"{option.style}{recommended_text}"
        )
        print("   标题：", option.title)
        print(
            "   内容：",
            option.content_preview,
        )
        print(
            "   回答 ID：",
            option.answer_id,
        )

    selected = options[
        choose_index(count=len(options))
    ]
    rating = choose_mapping(
        prompt=(
            "专业评价：0=不评价，1=专业，"
            "2=一般，3=不匹配："
        ),
        mapping=RATING_OPTIONS,
    )
    action = choose_mapping(
        prompt=(
            "使用行为：0=无，1=采纳，2=复制："
        ),
        mapping=ACTION_OPTIONS,
    )

    if rating is None and action is None:
        raise SystemExit(
            "至少需要选择一项评价或使用行为。"
        )

    comment = input(
        "补充意见（可直接回车跳过）："
    ).strip()

    path = record_feedback_for_option(
        option=selected,
        rating=rating,
        action=action,
        comment=comment or None,
        feedback_path=args.feedback_file,
    )

    print()
    print("反馈已记录：", path)
    print(
        "下一次运行会将历史反馈接入第七项评分。"
    )


if __name__ == "__main__":
    main()
