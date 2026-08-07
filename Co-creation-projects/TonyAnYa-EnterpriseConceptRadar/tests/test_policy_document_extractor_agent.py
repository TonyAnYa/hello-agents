"""测试大模型真实政策识别与标准化。"""

import json
from datetime import datetime, timezone

from enterprise_concept_radar.agents.policy_document_extractor_agent import (
    extract_policy_document,
)
from enterprise_concept_radar.services.web_fetcher import (
    FetchedWebPage,
)


def build_page() -> FetchedWebPage:
    """创建已完成真实抓取的网页材料。"""
    return FetchedWebPage(
        requested_url=(
            "https://93.184.216.34/policy"
        ),
        final_url=(
            "https://93.184.216.34/policy-final"
        ),
        status_code=200,
        content_type="text/html",
        title="关于测试政策的通知",
        text=(
            "关于测试政策的通知\n"
            "发布日期：2026年8月7日\n"
            "现就新能源项目管理有关事项通知如下。\n"
            "本通知自发布之日起实施。"
        ),
        html="<html>真实网页快照</html>",
        fetched_at=datetime(
            2026,
            8,
            7,
            tzinfo=timezone.utc,
        ),
    )


class PolicyAgent:
    """返回正式政策识别结果。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        assert "关于测试政策的通知" in input_text
        assert kwargs["max_tokens"] == 1400

        return json.dumps(
            {
                "is_policy": True,
                "title": "关于测试政策的通知",
                "issuing_authority": "国家能源局",
                "published_date": "2026-08-07",
                "document_type": "通知",
                "document_number": "测试〔2026〕1号",
                "confidence": 0.96,
                "evidence_quotes": [
                    "现就新能源项目管理有关事项通知如下。"
                ],
                "rejection_reason": None,
            },
            ensure_ascii=False,
        )


def test_extract_policy_document_uses_real_page_content() -> None:
    """身份字段来自 LLM，URL 和正文必须锁定为抓取结果。"""
    page = build_page()

    document = extract_policy_document(
        page=page,
        source_name_hint="国家能源局",
        source_slot=1,
        source_id="nea",
        user_question="有哪些新能源新政策？",
        keywords=["新能源"],
        agent=PolicyAgent(),
    )

    assert document is not None
    assert document.is_simulated is False
    assert document.title == "关于测试政策的通知"
    assert document.source_name == "国家能源局"
    assert str(document.source_url) == (
        "https://93.184.216.34/policy-final"
    )
    assert document.content == page.text
    assert (
        document.metadata["document_number"]
        == "测试〔2026〕1号"
    )


class NonPolicyAgent:
    """返回非政策识别结果。"""

    def run(
        self,
        input_text: str,
        **kwargs: object,
    ) -> str:
        return json.dumps(
            {
                "is_policy": False,
                "title": None,
                "issuing_authority": None,
                "published_date": None,
                "document_type": "其他",
                "document_number": None,
                "confidence": 0.92,
                "evidence_quotes": [],
                "rejection_reason": "网页为新闻报道。",
            },
            ensure_ascii=False,
        )


def test_non_policy_page_is_filtered() -> None:
    """新闻等非政策网页不应生成 PolicyDocument。"""
    document = extract_policy_document(
        page=build_page(),
        source_name_hint="国家能源局",
        source_slot=1,
        source_id="nea",
        agent=NonPolicyAgent(),
    )

    assert document is None
