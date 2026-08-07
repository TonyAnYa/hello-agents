"""交互式创建或修改政策追踪任务。"""

from __future__ import annotations

from pathlib import Path

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.output_paths import (
    normalize_user_path,
    resolve_output_directory,
)
from enterprise_concept_radar.tracking_tasks import (
    DEFAULT_OUTPUT_DIRECTORY,
    DateRangeConfig,
    DeliveryChannel,
    DeliveryTarget,
    TrackingSchedule,
    TrackingTask,
    load_tracking_task,
    save_tracking_task,
)

DEFAULT_QUESTION = (
    "今天有哪些能源政策出现了新的词语、"
    "新概念或制度安排，对广东电网有哪些潜在影响？"
)
DEFAULT_KEYWORDS = [
    "新能源",
    "新型电力系统",
    "电力市场",
    "绿电直连",
]


def parse_csv(
    raw_value: str,
) -> list[str]:
    """解析中文或英文逗号分隔内容。"""
    return [
        item.strip()
        for item in (
            raw_value
            .replace("，", ",")
            .split(",")
        )
        if item.strip()
    ]


def input_with_default(
    prompt: str,
    default: str,
) -> str:
    """提供清晰的交互默认值。"""
    value = input(
        f"{prompt}（默认：{default}）："
    ).strip()

    return value or default


def task_config_path(
    task_id: str,
) -> Path:
    """返回任务配置文件路径。"""
    return (
        RUNTIME_DATA_DIR
        / "tracking"
        / "tasks"
        / f"{task_id}.json"
    )


def load_existing_task(
    task_id: str,
) -> TrackingTask | None:
    """存在同名任务时读取并作为修改默认值。"""
    path = task_config_path(task_id)

    if not path.is_file():
        return None

    return load_tracking_task(path)


def main() -> None:
    """创建或修改用户可配置的追踪任务。"""
    print("=" * 64)
    print("EnterpriseConceptRadar 政策追踪任务配置")
    print("=" * 64)
    print(
        "政策来源读取 policy_sources.json；"
        "修改来源请运行 configure_policy_sources.py。"
    )
    print()

    task_id = input_with_default(
        "任务 ID",
        "energy-policy-radar",
    )
    existing = load_existing_task(
        task_id
    )

    if existing is not None:
        print(
            f"检测到既有任务，将修改："
            f"{task_config_path(task_id)}"
        )

    name = input_with_default(
        "任务名称",
        (
            existing.name
            if existing is not None
            else "能源政策新词新概念追踪"
        ),
    )
    question = input_with_default(
        "用户问题",
        (
            existing.question
            if existing is not None
            else DEFAULT_QUESTION
        ),
    )
    keywords_text = input_with_default(
        "关键词，使用逗号分隔",
        ",".join(
            existing.keywords
            if existing is not None
            else DEFAULT_KEYWORDS
        ),
    )
    exclude_text = input_with_default(
        "排除关键词，使用逗号分隔",
        ",".join(
            existing.exclude_keywords
            if existing is not None
            else [
                "招聘",
                "采购",
                "会议通知",
            ]
        ),
    )
    schedule_text = input_with_default(
        "每日执行时间，使用逗号分隔",
        ",".join(
            existing.schedule.times
            if existing is not None
            else [
                "08:30",
                "14:00",
            ]
        ),
    )
    timezone_name = input_with_default(
        "时区",
        (
            existing.schedule.timezone
            if existing is not None
            else "Asia/Shanghai"
        ),
    )
    output_directory_text = input_with_default(
        "Markdown/JSON 简报保存位置",
        (
            existing.output_directory
            if existing is not None
            else DEFAULT_OUTPUT_DIRECTORY
        ),
    )
    output_directory = normalize_user_path(
        output_directory_text
    )
    resolved_output_directory = (
        resolve_output_directory(
            output_directory,
            project_root=PROJECT_ROOT,
        )
    )
    lookback_days = int(
        input_with_default(
            "首次运行向前检索天数",
            str(
                existing.date_range.initial_lookback_days
                if existing is not None
                else 7
            ),
        )
    )
    overlap_hours = int(
        input_with_default(
            "后续运行重叠检索小时数",
            str(
                existing.date_range.overlap_hours
                if existing is not None
                else 36
            ),
        )
    )
    max_results = int(
        input_with_default(
            "每个政策源最大搜索结果数",
            str(
                existing.max_results_per_source
                if existing is not None
                else 8
            ),
        )
    )
    max_policies = int(
        input_with_default(
            "每次最大新增政策数",
            str(
                existing.max_policies_per_run
                if existing is not None
                else 12
            ),
        )
    )
    max_concepts = int(
        input_with_default(
            "每份政策最多深入分析概念数",
            str(
                existing.max_concepts_per_policy
                if existing is not None
                else 3
            ),
        )
    )
    max_intelligence_items = int(
        input_with_default(
            "每次最多生成完整概念情报项",
            str(
                existing.max_intelligence_items_per_run
                if existing is not None
                else 6
            ),
        )
    )

    task = TrackingTask(
        task_id=task_id,
        name=name,
        question=question,
        keywords=parse_csv(
            keywords_text
        ),
        exclude_keywords=parse_csv(
            exclude_text
        ),
        source_config_path=(
            existing.source_config_path
            if existing is not None
            else (
                "data/runtime/config/"
                "policy_sources.json"
            )
        ),
        output_directory=output_directory,
        date_range=DateRangeConfig(
            mode=(
                existing.date_range.mode
                if existing is not None
                else (
                    DateRangeConfig()
                    .mode
                )
            ),
            initial_lookback_days=(
                lookback_days
            ),
            overlap_hours=overlap_hours,
            rolling_days=(
                existing.date_range.rolling_days
                if existing is not None
                else 7
            ),
        ),
        schedule=TrackingSchedule(
            enabled=(
                existing.schedule.enabled
                if existing is not None
                else True
            ),
            timezone=timezone_name,
            times=parse_csv(
                schedule_text
            ),
            catch_up_minutes=(
                existing.schedule.catch_up_minutes
                if existing is not None
                else 90
            ),
        ),
        max_results_per_source=max_results,
        max_candidates_per_run=(
            existing.max_candidates_per_run
            if existing is not None
            else 24
        ),
        max_policies_per_run=max_policies,
        max_concepts_per_policy=max_concepts,
        max_intelligence_items_per_run=(
            max_intelligence_items
        ),
        minimum_concept_confidence=(
            existing.minimum_concept_confidence
            if existing is not None
            else 0.65
        ),
        minimum_novelty_score=(
            existing.minimum_novelty_score
            if existing is not None
            else 50
        ),
        only_new_policies=(
            existing.only_new_policies
            if existing is not None
            else True
        ),
        send_when_no_updates=(
            existing.send_when_no_updates
            if existing is not None
            else True
        ),
        delivery_targets=(
            existing.delivery_targets
            if existing is not None
            else [
                DeliveryTarget(
                    channel=(
                        DeliveryChannel.LOCAL
                    ),
                    name="本地政策简报",
                )
            ]
        ),
    )
    output_path = task_config_path(
        task.task_id
    )
    save_tracking_task(
        task,
        output_path,
    )

    print()
    print("=" * 64)
    print("追踪任务配置完成")
    print("=" * 64)
    print("任务文件：", output_path)
    print("问题：", task.question)
    print(
        "关键词：",
        "、".join(task.keywords),
    )
    print(
        "调度时间：",
        "、".join(task.schedule.times),
        task.schedule.timezone,
    )
    print(
        "简报保存位置：",
        resolved_output_directory,
    )


if __name__ == "__main__":
    main()
