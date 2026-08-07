"""测试本地双格式投递和预留渠道隔离。"""

import json
from datetime import date, datetime, timezone

from enterprise_concept_radar.delivery import (
    deliver_collection_run,
)
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
)
from enterprise_concept_radar.tracking_tasks import (
    DeliveryChannel,
    DeliveryTarget,
    TrackingTask,
)


def build_run() -> PolicyCollectionRun:
    """创建没有新政策的运行结果。"""
    now = datetime.now(timezone.utc)

    return PolicyCollectionRun(
        task_id="energy-policy-radar",
        run_id="run-1",
        started_at=now,
        completed_at=now,
        published_after=date(2026, 8, 1),
        published_before=date(2026, 8, 7),
        searched_candidate_count=0,
        fetched_page_count=0,
        llm_call_count=0,
        duplicate_count=0,
        previously_delivered_count=0,
    )


def build_task() -> TrackingTask:
    """创建默认本地投递任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些政策？",
        keywords=["新能源"],
    )


def test_local_delivery_creates_two_report_formats(
    tmp_path,
) -> None:
    """本地渠道应同时生成 Markdown 和 JSON。"""
    receipts = deliver_collection_run(
        task=build_task(),
        run=build_run(),
        output_dir=tmp_path,
    )

    assert receipts[0].success is True
    assert (
        tmp_path / "policy_brief.md"
    ).is_file()
    assert (
        tmp_path / "policy_brief.json"
    ).is_file()
    assert (
        tmp_path / "delivery_receipts.json"
    ).is_file()


def test_policy_brief_json_is_structured(
    tmp_path,
) -> None:
    """JSON 简报应包含任务、汇总和政策数组。"""
    deliver_collection_run(
        task=build_task(),
        run=build_run(),
        output_dir=tmp_path,
    )
    payload = json.loads(
        (
            tmp_path / "policy_brief.json"
        ).read_text(encoding="utf-8")
    )

    assert payload["schema_version"] == "1.0"
    assert payload["task"]["task_id"] == (
        "energy-policy-radar"
    )
    assert payload["summary"]["new_policy_count"] == 0
    assert payload["policies"] == []


def test_no_updates_can_skip_actual_delivery(
    tmp_path,
) -> None:
    """用户关闭空简报后应记录成功跳过。"""
    task = build_task().model_copy(
        update={
            "send_when_no_updates": False,
        }
    )
    receipts = deliver_collection_run(
        task=task,
        run=build_run(),
        output_dir=tmp_path,
    )

    assert receipts[0].success is True
    assert receipts[0].skipped is True
    assert not (
        tmp_path / "policy_brief.md"
    ).exists()


def test_reserved_platform_failure_does_not_break_local(
    tmp_path,
) -> None:
    """预留平台未配置时不应影响本地报告。"""
    task = build_task().model_copy(
        update={
            "delivery_targets": [
                DeliveryTarget(
                    channel=(
                        DeliveryChannel.LOCAL
                    ),
                    name="本地报告",
                ),
                DeliveryTarget(
                    channel=(
                        DeliveryChannel.FEISHU
                    ),
                    name="飞书",
                ),
            ]
        }
    )
    receipts = deliver_collection_run(
        task=task,
        run=build_run(),
        output_dir=tmp_path,
    )

    assert [item.success for item in receipts] == [
        True,
        False,
    ]
