"""测试政策拒绝原因和网页编码审计。"""

import json

from enterprise_concept_radar.delivery import (
    build_collection_markdown,
)
from enterprise_concept_radar.policy_collection import (
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

URL = "https://93.184.216.34/policy"


def fake_search(**kwargs):
    """返回一个真实候选 URL 替身。"""
    source = kwargs["source"]

    return [
        PolicySearchResult(
            source_slot=source.slot,
            source_id=source.source_id,
            source_name=source.name or "全网",
            source_kind=source.kind,
            position=1,
            title="能源行业会议新闻",
            url=URL,
            snippet="会议报道。",
            query="测试查询",
        )
    ]


def fake_fetch(url: str) -> FetchedWebPage:
    """返回编码正常的新闻网页。"""
    assert url == URL

    return FetchedWebPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        encoding="utf-8",
        title="能源行业会议新闻",
        text=(
            "能源行业会议新闻\n"
            "有关单位召开会议并介绍近期工作进展。\n"
            "本页面是新闻报道，不是正式政策正文。"
        ),
        html="<html>新闻报道</html>",
    )


class NonPolicyAgent:
    """返回带明确原因的非政策判断。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        assert '"encoding": "utf-8"' in input_text

        return json.dumps(
            {
                "is_policy": False,
                "title": None,
                "issuing_authority": None,
                "published_date": None,
                "document_type": "其他",
                "document_number": None,
                "confidence": 0.94,
                "evidence_quotes": [],
                "rejection_reason": (
                    "网页为会议新闻报道，"
                    "不包含正式政策正文。"
                ),
            },
            ensure_ascii=False,
        )


def test_rejection_is_auditable_in_collection_brief() -> None:
    """非政策候选应保存原因、置信度和网页编码。"""
    task = TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="近期有哪些能源政策？",
        keywords=["新能源"],
    )
    run = collect_online_policies(
        task=task,
        source_selection=(
            build_policy_source_selection(
                enabled_slots={1}
            )
        ),
        state=TrackingTaskState(
            task_id=task.task_id
        ),
        search_func=fake_search,
        fetch_func=fake_fetch,
        extractor_agent=NonPolicyAgent(),
    )

    assert run.documents == []
    assert len(run.failures) == 1
    failure = run.failures[0]
    assert failure.stage == "policy_rejected"
    assert "会议新闻报道" in failure.message
    assert "识别置信度：0.94" in failure.message
    assert "网页编码：utf-8" in failure.message

    markdown = build_collection_markdown(
        task=task,
        run=run,
    )
    assert "均未通过正式政策准入" in markdown
    assert "会议新闻报道" in markdown
