"""测试多来源政策采集、LLM 调用计数与去重。"""

from datetime import datetime, timezone

from enterprise_concept_radar.models import (
    PolicyDocument,
    PolicyDocumentType,
)
from enterprise_concept_radar.policy_collection import (
    build_policy_fingerprint,
    collect_online_policies,
)
from enterprise_concept_radar.policy_sources import (
    build_policy_source_selection,
)
from enterprise_concept_radar.services.policy_search import (
    PolicySearchResult,
)
from enterprise_concept_radar.services.web_fetcher import (
    FetchedWebPage,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
    TrackingTaskState,
)


def build_task() -> TrackingTask:
    """创建采集测试任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些新能源政策？",
        keywords=["新能源"],
        max_results_per_source=2,
        max_candidates_per_run=5,
        max_policies_per_run=5,
    )


def fake_search(**kwargs):
    """每个来源返回同一政策 URL。"""
    source = kwargs["source"]

    return [
        PolicySearchResult(
            source_slot=source.slot,
            source_id=source.source_id,
            source_name=source.name or "全网",
            source_kind=source.kind,
            position=1,
            title="关于测试政策的通知",
            url=(
                "https://93.184.216.34/policy"
            ),
            snippet="新能源测试政策。",
            query="测试查询",
        )
    ]


def fake_fetch(url: str) -> FetchedWebPage:
    """返回真实抓取页面替身。"""
    return FetchedWebPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        title="关于测试政策的通知",
        text=(
            "关于测试政策的通知\n"
            "现就新能源项目有关事项通知如下。\n"
            "本通知自发布之日起实施。"
        ),
        html="<html>测试政策正文</html>",
    )


def fake_extract(**kwargs):
    """模拟 LLM 已完成政策身份提取。"""
    page = kwargs["page"]
    source_id = kwargs["source_id"]
    source_slot = kwargs["source_slot"]

    return PolicyDocument(
        document_id=f"online-{source_id}",
        title="关于测试政策的通知",
        source_name="国家能源局",
        source_url=page.final_url,
        published_date="2026-08-07",
        document_type=PolicyDocumentType.NOTICE,
        content=page.text,
        is_simulated=False,
        metadata={
            "document_number": "国能发〔2026〕1号",
            "content_sha256": "same-content",
            "source_id": source_id,
            "source_slot": source_slot,
            "requested_url": page.requested_url,
            "final_url": page.final_url,
            "search_query": "测试查询",
        },
    )


def test_collection_calls_extractor_and_deduplicates(
    tmp_path,
) -> None:
    """同一 URL 不应重复抓取和调用 LLM。"""
    run = collect_online_policies(
        task=build_task(),
        source_selection=(
            build_policy_source_selection()
        ),
        state=TrackingTaskState(
            task_id="energy-policy-radar"
        ),
        now=datetime(
            2026,
            8,
            7,
            8,
            30,
            tzinfo=timezone.utc,
        ),
        artifact_dir=tmp_path,
        search_func=fake_search,
        fetch_func=fake_fetch,
        extract_func=fake_extract,
    )

    assert len(run.documents) == 1
    assert run.fetched_page_count == 1
    assert run.llm_call_count == 1
    assert run.duplicate_count == 1


def test_previously_delivered_policy_is_filtered() -> None:
    """已经成功投递的政策不应再次发送。"""
    document = fake_extract(
        page=fake_fetch(
            "https://93.184.216.34/policy"
        ),
        source_id="nea",
        source_slot=1,
    )
    fingerprint = build_policy_fingerprint(
        document
    )
    state = TrackingTaskState(
        task_id="energy-policy-radar",
        delivered_fingerprints=[
            fingerprint,
        ],
    )
    run = collect_online_policies(
        task=build_task(),
        source_selection=(
            build_policy_source_selection(
                enabled_slots={1}
            )
        ),
        state=state,
        search_func=fake_search,
        fetch_func=fake_fetch,
        extract_func=fake_extract,
    )

    assert run.documents == []
    assert run.previously_delivered_count == 1


def test_collection_saves_raw_snapshot(
    tmp_path,
) -> None:
    """抓取页面应保存原始 HTML 和清洗文本。"""
    collect_online_policies(
        task=build_task(),
        source_selection=(
            build_policy_source_selection(
                enabled_slots={1}
            )
        ),
        state=TrackingTaskState(
            task_id="energy-policy-radar"
        ),
        artifact_dir=tmp_path,
        search_func=fake_search,
        fetch_func=fake_fetch,
        extract_func=fake_extract,
    )

    assert list(
        (tmp_path / "raw_pages").glob("*.html")
    )
    assert list(
        (tmp_path / "raw_pages").glob("*.txt")
    )
