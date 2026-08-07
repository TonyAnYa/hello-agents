"""测试完整智能简报、本地投递和通用 Webhook。"""

from datetime import date, datetime, timezone

from enterprise_concept_radar.delivery import (
    GenericWebhookDelivery,
    deliver_collection_run,
    deliver_tracking_run,
)
from enterprise_concept_radar.intelligence_pipeline import (
    PolicyIntelligenceRun,
)
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
)
from enterprise_concept_radar.tracking_tasks import (
    DeliveryChannel,
    DeliveryTarget,
    TrackingTask,
)


def build_collection_run() -> PolicyCollectionRun:
    """创建没有新增政策的采集结果。"""
    now = datetime.now(timezone.utc)

    return PolicyCollectionRun(
        task_id="energy-policy-radar",
        run_id="collection-1",
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


def build_intelligence_run() -> PolicyIntelligenceRun:
    """创建没有概念候选的智能分析结果。"""
    now = datetime.now(timezone.utc)

    return PolicyIntelligenceRun(
        task_id="energy-policy-radar",
        collection_run_id="collection-1",
        started_at=now,
        completed_at=now,
        document_count=0,
        analyzed_document_count=0,
        llm_stage_count=0,
    )


def build_task() -> TrackingTask:
    """创建默认本地投递任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些政策？",
        keywords=["新能源"],
    )


def test_local_delivery_creates_full_briefs(
    tmp_path,
) -> None:
    """本地渠道应同时生成采集和智能分析双格式简报。"""
    receipts = deliver_tracking_run(
        task=build_task(),
        collection_run=build_collection_run(),
        intelligence_run=(
            build_intelligence_run()
        ),
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
        tmp_path / "intelligence_brief.md"
    ).is_file()
    assert (
        tmp_path / "intelligence_brief.json"
    ).is_file()
    assert receipts[0].destination.endswith(
        "intelligence_brief.md"
    )


def test_no_updates_can_skip_all_delivery(
    tmp_path,
) -> None:
    """关闭空简报后应记录成功跳过。"""
    task = build_task().model_copy(
        update={
            "send_when_no_updates": False,
        }
    )
    receipts = deliver_tracking_run(
        task=task,
        collection_run=build_collection_run(),
        intelligence_run=(
            build_intelligence_run()
        ),
        output_dir=tmp_path,
    )

    assert receipts[0].success is True
    assert receipts[0].skipped is True
    assert not (
        tmp_path / "policy_brief.md"
    ).exists()


class FakeResponse:
    """模拟成功的 HTTP 响应。"""

    def raise_for_status(self) -> None:
        """成功响应不抛异常。"""


class FakeSession:
    """记录 Webhook 请求内容。"""

    def __init__(self) -> None:
        self.payload = None
        self.endpoint = None

    def post(
        self,
        endpoint,
        *,
        headers,
        json,
        timeout,
    ):
        self.endpoint = endpoint
        self.payload = json
        assert headers[
            "Content-Type"
        ] == "application/json"
        assert timeout == 30

        return FakeResponse()


def test_webhook_receives_intelligence_payload(
    tmp_path,
    monkeypatch,
) -> None:
    """通用 Webhook 应收到 2.0 完整智能数据包。"""
    monkeypatch.setenv(
        "TEST_WEBHOOK_ENDPOINT",
        "https://example.com/webhook",
    )
    session = FakeSession()
    task = build_task().model_copy(
        update={
            "delivery_targets": [
                DeliveryTarget(
                    channel=(
                        DeliveryChannel
                        .GENERIC_WEBHOOK
                    ),
                    name="测试 Webhook",
                    endpoint_env=(
                        "TEST_WEBHOOK_ENDPOINT"
                    ),
                )
            ]
        }
    )
    receipts = deliver_tracking_run(
        task=task,
        collection_run=build_collection_run(),
        intelligence_run=(
            build_intelligence_run()
        ),
        output_dir=tmp_path,
        adapters={
            DeliveryChannel.GENERIC_WEBHOOK: (
                GenericWebhookDelivery(
                    session=session
                )
            )
        },
    )

    assert receipts[0].success is True
    assert session.payload[
        "schema_version"
    ] == "2.0"
    assert (
        session.payload["intelligence"]
        is not None
    )


def test_reserved_platform_does_not_break_local(
    tmp_path,
) -> None:
    """预留平台失败不应影响本地完整简报。"""
    task = build_task().model_copy(
        update={
            "delivery_targets": [
                DeliveryTarget(
                    channel=DeliveryChannel.LOCAL,
                    name="本地报告",
                ),
                DeliveryTarget(
                    channel=DeliveryChannel.FEISHU,
                    name="飞书",
                ),
            ]
        }
    )
    receipts = deliver_tracking_run(
        task=task,
        collection_run=build_collection_run(),
        intelligence_run=(
            build_intelligence_run()
        ),
        output_dir=tmp_path,
    )

    assert [
        receipt.success
        for receipt in receipts
    ] == [True, False]


def test_legacy_collection_delivery_still_works(
    tmp_path,
) -> None:
    """旧的仅采集投递入口应保持兼容。"""
    receipts = deliver_collection_run(
        task=build_task(),
        run=build_collection_run(),
        output_dir=tmp_path,
    )

    assert receipts[0].success is True
    assert (
        tmp_path / "policy_brief.md"
    ).is_file()
