"""面向最终客户的一键推荐配置。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.output_paths import (
    resolve_output_directory,
)
from enterprise_concept_radar.policy_sources import (
    PolicySourceSelection,
    build_policy_source_selection,
    save_policy_source_selection,
)
from enterprise_concept_radar.tracking_tasks import (
    DEFAULT_OUTPUT_DIRECTORY,
    DateRangeConfig,
    DeliveryChannel,
    DeliveryTarget,
    TrackingSchedule,
    TrackingTask,
    save_tracking_task,
)

DEFAULT_TASK_ID = "energy-policy-radar"
DEFAULT_TASK_NAME = "能源政策新词新概念追踪"
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
DEFAULT_EXCLUDE_KEYWORDS = [
    "招聘",
    "采购",
    "会议通知",
]


@dataclass(frozen=True, slots=True)
class CustomerSetupResult:
    """客户推荐配置的保存结果。"""

    source_path: Path
    task_path: Path
    output_directory: Path
    source_selection: PolicySourceSelection
    task: TrackingTask


def recommended_source_path() -> Path:
    """返回推荐政策源配置路径。"""
    return (
        RUNTIME_DATA_DIR
        / "config"
        / "policy_sources.json"
    )


def recommended_task_path() -> Path:
    """返回推荐追踪任务路径。"""
    return (
        RUNTIME_DATA_DIR
        / "tracking"
        / "tasks"
        / f"{DEFAULT_TASK_ID}.json"
    )


def build_recommended_task(
    *,
    output_directory: str = (
        DEFAULT_OUTPUT_DIRECTORY
    ),
) -> TrackingTask:
    """生成面向普通客户的推荐任务。"""
    return TrackingTask(
        task_id=DEFAULT_TASK_ID,
        name=DEFAULT_TASK_NAME,
        question=DEFAULT_QUESTION,
        keywords=list(DEFAULT_KEYWORDS),
        exclude_keywords=list(
            DEFAULT_EXCLUDE_KEYWORDS
        ),
        source_config_path=(
            "data/runtime/config/"
            "policy_sources.json"
        ),
        output_directory=output_directory,
        date_range=DateRangeConfig(
            initial_lookback_days=7,
            overlap_hours=36,
            rolling_days=7,
        ),
        schedule=TrackingSchedule(
            enabled=True,
            timezone="Asia/Shanghai",
            times=[
                "08:30",
                "14:00",
            ],
            catch_up_minutes=90,
        ),
        max_results_per_source=8,
        max_candidates_per_run=24,
        max_policies_per_run=12,
        max_concepts_per_policy=3,
        max_intelligence_items_per_run=6,
        minimum_concept_confidence=0.65,
        minimum_novelty_score=50,
        only_new_policies=True,
        send_when_no_updates=True,
        delivery_targets=[
            DeliveryTarget(
                channel=(
                    DeliveryChannel.LOCAL
                ),
                name="本地政策智能简报",
            )
        ],
    )


def apply_recommended_customer_setup(
    *,
    output_directory: str = (
        DEFAULT_OUTPUT_DIRECTORY
    ),
    enable_open_web: bool = False,
    project_root: str | Path = PROJECT_ROOT,
) -> CustomerSetupResult:
    """保存推荐来源、追踪任务并创建报告目录。"""
    enabled_slots = {
        1,
        2,
    }

    if enable_open_web:
        enabled_slots.add(6)

    source_selection = (
        build_policy_source_selection(
            enabled_slots=enabled_slots
        )
    )
    source_path = (
        recommended_source_path()
    )
    save_policy_source_selection(
        source_selection,
        source_path,
    )

    task = build_recommended_task(
        output_directory=output_directory
    )
    task_path = recommended_task_path()
    save_tracking_task(
        task,
        task_path,
    )
    resolved_output = resolve_output_directory(
        task.output_directory,
        project_root=project_root,
    )

    return CustomerSetupResult(
        source_path=source_path,
        task_path=task_path,
        output_directory=resolved_output,
        source_selection=source_selection,
        task=task,
    )
