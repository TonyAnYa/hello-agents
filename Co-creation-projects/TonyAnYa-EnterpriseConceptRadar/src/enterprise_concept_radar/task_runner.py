"""执行一次完整在线追踪与智能分析任务。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.delivery import (
    DeliveryReceipt,
    deliver_tracking_run,
)
from enterprise_concept_radar.intelligence_pipeline import (
    PolicyIntelligenceRun,
    run_policy_intelligence,
    save_policy_intelligence_run,
)
from enterprise_concept_radar.output_paths import (
    build_tracking_output_paths,
    publish_latest_files,
)
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
    build_policy_fingerprint,
    collect_online_policies,
    save_collection_run,
)
from enterprise_concept_radar.policy_sources import (
    load_policy_source_selection,
)
from enterprise_concept_radar.run_lock import (
    task_run_lock,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
    TrackingTaskState,
    load_tracking_state,
    load_tracking_task,
    save_tracking_state,
)


class TrackingExecutionError(RuntimeError):
    """追踪任务执行失败。"""


class TrackingTaskExecution(BaseModel):
    """一次任务执行的汇总结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task: TrackingTask
    collection_run: PolicyCollectionRun
    intelligence_run: PolicyIntelligenceRun
    delivery_receipts: list[DeliveryReceipt]
    state: TrackingTaskState
    output_dir: str = Field(
        min_length=1,
    )
    latest_dir: str = Field(
        min_length=1,
    )


def resolve_project_path(
    value: str | Path,
) -> Path:
    """将任务中的相对路径解析到项目根目录。"""
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def tracking_state_path(
    task_id: str,
) -> Path:
    """返回任务状态文件路径。"""
    return (
        RUNTIME_DATA_DIR
        / "tracking"
        / "state"
        / f"{task_id}.json"
    )


def _execute_tracking_task(
    *,
    task: TrackingTask,
    now: datetime | None = None,
) -> TrackingTaskExecution:
    """在已取得互斥锁的前提下执行完整任务。"""
    state_path = tracking_state_path(
        task.task_id
    )
    state = load_tracking_state(
        state_path,
        task_id=task.task_id,
    )
    started_at = (
        now
        or datetime.now(timezone.utc)
    )
    state = state.model_copy(
        update={
            "last_started_at": started_at,
            "last_error": None,
        }
    )
    save_tracking_state(
        state,
        state_path,
    )

    try:
        output_paths = (
            build_tracking_output_paths(
                task=task,
                started_at=started_at,
            )
        )
        source_selection = (
            load_policy_source_selection(
                resolve_project_path(
                    task.source_config_path
                )
            )
        )
        collection_run = (
            collect_online_policies(
                task=task,
                source_selection=(
                    source_selection
                ),
                state=state,
                now=started_at,
                artifact_dir=(
                    output_paths.run_directory
                ),
            )
        )
        save_collection_run(
            collection_run,
            output_paths.run_directory,
        )

        intelligence_run = (
            run_policy_intelligence(
                task=task,
                collection_run=collection_run,
            )
        )
        save_policy_intelligence_run(
            task=task,
            run=intelligence_run,
            output_dir=(
                output_paths.run_directory
            ),
        )

        receipts = deliver_tracking_run(
            task=task,
            collection_run=collection_run,
            intelligence_run=intelligence_run,
            output_dir=(
                output_paths.run_directory
            ),
        )
        successful_delivery = any(
            receipt.success
            for receipt in receipts
        )

        if not successful_delivery:
            raise TrackingExecutionError(
                "所有投递渠道均失败"
            )

        publish_latest_files(
            run_directory=(
                output_paths.run_directory
            ),
            latest_directory=(
                output_paths.latest_directory
            ),
        )

        delivered_fingerprints = list(
            state.delivered_fingerprints
        )
        delivered_content = any(
            receipt.success
            and not receipt.skipped
            for receipt in receipts
        )

        if delivered_content:
            for document in (
                collection_run.documents
            ):
                fingerprint = (
                    build_policy_fingerprint(
                        document
                    )
                )

                if (
                    fingerprint
                    not in delivered_fingerprints
                ):
                    delivered_fingerprints.append(
                        fingerprint
                    )

        state = state.model_copy(
            update={
                "last_successful_at": (
                    collection_run.completed_at
                ),
                "delivered_fingerprints": (
                    delivered_fingerprints
                ),
                "failed_runs": 0,
                "last_error": None,
            }
        )
        save_tracking_state(
            state,
            state_path,
        )

        return TrackingTaskExecution(
            task=task,
            collection_run=collection_run,
            intelligence_run=intelligence_run,
            delivery_receipts=receipts,
            state=state,
            output_dir=str(
                output_paths.run_directory
            ),
            latest_dir=str(
                output_paths.latest_directory
            ),
        )
    except Exception as exc:
        failed_state = state.model_copy(
            update={
                "failed_runs": (
                    state.failed_runs + 1
                ),
                "last_error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }
        )
        save_tracking_state(
            failed_state,
            state_path,
        )
        raise


def run_tracking_task(
    task_path: str | Path,
    *,
    now: datetime | None = None,
) -> TrackingTaskExecution:
    """取得互斥锁后执行采集、分析、投递和状态更新。"""
    task = load_tracking_task(task_path)

    with task_run_lock(task.task_id):
        return _execute_tracking_task(
            task=task,
            now=now,
        )
