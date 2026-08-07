"""政策采集结果的统一投递接口与本地双格式报告。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import requests
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from enterprise_concept_radar.models import PolicyDocument
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
)
from enterprise_concept_radar.tracking_tasks import (
    DeliveryChannel,
    DeliveryTarget,
    TrackingTask,
)


class DeliveryError(RuntimeError):
    """投递失败或渠道未配置。"""


class DeliveryReceipt(BaseModel):
    """一个投递目标的执行回执。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    channel: DeliveryChannel
    target_name: str = Field(
        min_length=1,
    )
    success: bool
    skipped: bool = Field(
        default=False,
        description="是否因没有更新而跳过实际投递",
    )
    delivered_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )
    destination: str | None = None
    message: str = Field(
        min_length=1,
    )


class DeliveryAdapter(Protocol):
    """统一投递适配器接口。"""

    def deliver(
        self,
        *,
        task: TrackingTask,
        run: PolicyCollectionRun,
        target: DeliveryTarget,
        output_dir: Path,
    ) -> DeliveryReceipt:
        """投递一次政策采集结果。"""


def _document_summary(
    document: PolicyDocument,
) -> dict[str, Any]:
    """生成简报 JSON 中的政策摘要，不重复保存全文。"""
    metadata = document.metadata

    return {
        "document_id": document.document_id,
        "title": document.title,
        "source_name": document.source_name,
        "source_url": str(document.source_url),
        "published_date": (
            document.published_date.isoformat()
        ),
        "document_type": (
            document.document_type.value
        ),
        "document_number": metadata.get(
            "document_number"
        ),
        "content_sha256": metadata.get(
            "content_sha256"
        ),
        "llm_policy_confidence": metadata.get(
            "llm_policy_confidence"
        ),
        "evidence_quotes": metadata.get(
            "llm_evidence_quotes",
            [],
        ),
        "snapshot_path": metadata.get(
            "snapshot_path"
        ),
    }


def build_collection_markdown(
    *,
    task: TrackingTask,
    run: PolicyCollectionRun,
) -> str:
    """生成适合本地归档和平台推送的政策简报。"""
    lines = [
        f"# {task.name}",
        "",
        f"- 任务 ID：`{task.task_id}`",
        f"- 用户问题：{task.question}",
        (
            "- 检索时间范围："
            f"{run.published_after.isoformat()} "
            f"至 {run.published_before.isoformat()}"
        ),
        f"- 搜索候选：{run.searched_candidate_count}",
        f"- 已抓取网页：{run.fetched_page_count}",
        f"- LLM 政策识别调用：{run.llm_call_count}",
        f"- 本次新增真实政策：{len(run.documents)}",
        "",
    ]

    if not run.documents:
        lines.extend(
            [
                "## 运行结果",
                "",
                "本次未发现尚未投递的新政策。",
                "",
            ]
        )

    for index, document in enumerate(
        run.documents,
        start=1,
    ):
        document_number = (
            document.metadata.get(
                "document_number"
            )
            or "未识别"
        )
        confidence = document.metadata.get(
            "llm_policy_confidence"
        )

        lines.extend(
            [
                f"## {index}. {document.title}",
                "",
                f"- 发布机构：{document.source_name}",
                (
                    "- 发布日期："
                    f"{document.published_date.isoformat()}"
                ),
                (
                    "- 文件类型："
                    f"{document.document_type.value}"
                ),
                f"- 文号：{document_number}",
                f"- 权威来源：{document.source_url}",
                (
                    "- LLM 政策识别置信度："
                    f"{confidence}"
                ),
                "",
            ]
        )

        evidence = document.metadata.get(
            "llm_evidence_quotes"
        )

        if isinstance(evidence, list) and evidence:
            lines.append("### 识别证据")
            lines.append("")

            for quote in evidence:
                lines.append(f"- {quote}")

            lines.append("")

    if run.failures:
        lines.extend(
            [
                "## 采集异常",
                "",
            ]
        )

        for failure in run.failures:
            location = (
                f"；URL：{failure.url}"
                if failure.url
                else ""
            )
            lines.append(
                f"- {failure.source_id} / "
                f"{failure.stage}："
                f"{failure.error_type}："
                f"{failure.message}{location}"
            )

        lines.append("")

    lines.extend(
        [
            "## 说明",
            "",
            (
                "本报告中的政策正文来自实时网页抓取；"
                "政策身份字段由大模型依据网页材料提取，"
                "重要业务使用前仍需专业核验。"
            ),
            "",
        ]
    )

    return "\n".join(lines)


def build_collection_payload(
    *,
    task: TrackingTask,
    run: PolicyCollectionRun,
) -> dict[str, Any]:
    """生成 Markdown、Webhook 和平台适配器共用的数据包。"""
    markdown = build_collection_markdown(
        task=task,
        run=run,
    )

    return {
        "schema_version": "1.0",
        "generated_at": (
            run.completed_at.isoformat()
        ),
        "task": {
            "task_id": task.task_id,
            "name": task.name,
            "question": task.question,
            "keywords": task.keywords,
            "exclude_keywords": (
                task.exclude_keywords
            ),
            "timezone": task.schedule.timezone,
            "schedule_times": (
                task.schedule.times
            ),
        },
        "summary": {
            "published_after": (
                run.published_after.isoformat()
            ),
            "published_before": (
                run.published_before.isoformat()
            ),
            "searched_candidate_count": (
                run.searched_candidate_count
            ),
            "fetched_page_count": (
                run.fetched_page_count
            ),
            "llm_call_count": run.llm_call_count,
            "new_policy_count": len(
                run.documents
            ),
            "duplicate_count": (
                run.duplicate_count
            ),
            "previously_delivered_count": (
                run.previously_delivered_count
            ),
            "failure_count": len(run.failures),
        },
        "policies": [
            _document_summary(document)
            for document in run.documents
        ],
        "source_statuses": [
            status.model_dump(
                mode="json",
                exclude_none=True,
            )
            for status in run.source_statuses
        ],
        "failures": [
            failure.model_dump(
                mode="json",
                exclude_none=True,
            )
            for failure in run.failures
        ],
        "report_markdown": markdown,
    }


class LocalReportDelivery:
    """保存 Markdown 和 JSON 两种本地政策简报。"""

    def deliver(
        self,
        *,
        task: TrackingTask,
        run: PolicyCollectionRun,
        target: DeliveryTarget,
        output_dir: Path,
    ) -> DeliveryReceipt:
        """将双格式简报写入用户指定的运行目录。"""
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        payload = build_collection_payload(
            task=task,
            run=run,
        )
        markdown_path = (
            output_dir / "policy_brief.md"
        )
        json_path = (
            output_dir / "policy_brief.json"
        )
        markdown_path.write_text(
            str(payload["report_markdown"]),
            encoding="utf-8",
        )
        json_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return DeliveryReceipt(
            channel=target.channel,
            target_name=target.name,
            success=True,
            destination=str(markdown_path),
            message=(
                "本地 Markdown/JSON 政策简报已生成"
            ),
        )


class GenericWebhookDelivery:
    """通用 JSON Webhook 投递实现。"""

    def __init__(
        self,
        *,
        timeout: int = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = (
            session or requests.Session()
        )

    def deliver(
        self,
        *,
        task: TrackingTask,
        run: PolicyCollectionRun,
        target: DeliveryTarget,
        output_dir: Path,
    ) -> DeliveryReceipt:
        """从环境变量读取地址和令牌并发送 JSON。"""
        del output_dir

        if not target.endpoint_env:
            raise DeliveryError(
                "通用 Webhook 缺少 endpoint_env"
            )

        endpoint = os.getenv(
            target.endpoint_env,
            "",
        ).strip()

        if not endpoint:
            raise DeliveryError(
                "未找到 Webhook 地址环境变量："
                f"{target.endpoint_env}"
            )

        headers = {
            "Content-Type": "application/json",
        }

        if target.token_env:
            token = os.getenv(
                target.token_env,
                "",
            ).strip()

            if not token:
                raise DeliveryError(
                    "未找到 Webhook 令牌环境变量："
                    f"{target.token_env}"
                )

            headers["Authorization"] = (
                f"Bearer {token}"
            )

        try:
            response = self.session.post(
                endpoint,
                headers=headers,
                json=build_collection_payload(
                    task=task,
                    run=run,
                ),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DeliveryError(
                "Webhook 投递失败："
                f"{type(exc).__name__}: {exc}"
            ) from exc

        return DeliveryReceipt(
            channel=target.channel,
            target_name=target.name,
            success=True,
            destination=endpoint,
            message="Webhook 投递成功",
        )


class ReservedPlatformDelivery:
    """企业微信、钉钉、飞书和其他平台的预留适配器。"""

    def deliver(
        self,
        *,
        task: TrackingTask,
        run: PolicyCollectionRun,
        target: DeliveryTarget,
        output_dir: Path,
    ) -> DeliveryReceipt:
        """取得平台接口规范前明确返回未配置。"""
        del task, run, output_dir

        raise DeliveryError(
            f"{target.channel.value} 投递接口尚未配置"
        )


def default_delivery_adapters(
) -> Mapping[DeliveryChannel, DeliveryAdapter]:
    """返回当前项目支持的默认适配器。"""
    reserved = ReservedPlatformDelivery()

    return {
        DeliveryChannel.LOCAL: (
            LocalReportDelivery()
        ),
        DeliveryChannel.GENERIC_WEBHOOK: (
            GenericWebhookDelivery()
        ),
        DeliveryChannel.EMAIL: reserved,
        DeliveryChannel.WECOM: reserved,
        DeliveryChannel.DINGTALK: reserved,
        DeliveryChannel.FEISHU: reserved,
        DeliveryChannel.ENTERPRISE_BRAIN: (
            reserved
        ),
    }


def _save_receipts(
    *,
    receipts: list[DeliveryReceipt],
    output_dir: Path,
) -> Path:
    """保存全部渠道回执。"""
    receipts_path = (
        output_dir / "delivery_receipts.json"
    )
    receipts_path.write_text(
        json.dumps(
            [
                receipt.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for receipt in receipts
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return receipts_path


def deliver_collection_run(
    *,
    task: TrackingTask,
    run: PolicyCollectionRun,
    output_dir: str | Path,
    adapters: Mapping[
        DeliveryChannel,
        DeliveryAdapter,
    ] | None = None,
) -> list[DeliveryReceipt]:
    """向全部目标投递；单个渠道失败不影响其他渠道。"""
    directory = Path(output_dir)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    active_adapters = (
        adapters
        or default_delivery_adapters()
    )
    enabled_targets = [
        target
        for target in task.delivery_targets
        if target.enabled
    ]

    if (
        not run.documents
        and not task.send_when_no_updates
    ):
        skipped_receipts = [
            DeliveryReceipt(
                channel=target.channel,
                target_name=target.name,
                success=True,
                skipped=True,
                message=(
                    "没有新增政策，按照任务配置跳过投递"
                ),
            )
            for target in enabled_targets
        ]
        _save_receipts(
            receipts=skipped_receipts,
            output_dir=directory,
        )

        return skipped_receipts

    receipts: list[DeliveryReceipt] = []

    for target in enabled_targets:
        adapter = active_adapters.get(
            target.channel
        )

        if adapter is None:
            receipts.append(
                DeliveryReceipt(
                    channel=target.channel,
                    target_name=target.name,
                    success=False,
                    message="没有可用的投递适配器",
                )
            )
            continue

        try:
            receipt = adapter.deliver(
                task=task,
                run=run,
                target=target,
                output_dir=directory,
            )
        except Exception as exc:
            receipt = DeliveryReceipt(
                channel=target.channel,
                target_name=target.name,
                success=False,
                message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        receipts.append(receipt)

    _save_receipts(
        receipts=receipts,
        output_dir=directory,
    )

    return receipts
