"""按用户问题、关键词、时间范围和政策来源搜索真实政策。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from urllib.parse import urlparse

import requests
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from enterprise_concept_radar.policy_sources import (
    PolicySourceKind,
    PolicySourceSlot,
    validate_policy_source_url,
)
from enterprise_concept_radar.services.source_search import (
    PolicySourceSearchError,
    resolve_serpapi_api_key,
)

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


class PolicySearchResult(BaseModel):
    """搜索引擎返回的一个候选政策网页。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    source_slot: int = Field(
        ge=1,
        le=6,
        description="来源选项编号",
    )
    source_id: str = Field(
        min_length=1,
        description="来源内部标识",
    )
    source_name: str = Field(
        min_length=1,
        description="来源显示名称",
    )
    source_kind: PolicySourceKind = Field(
        description="来源类型",
    )
    position: int = Field(
        ge=1,
        description="搜索结果位置",
    )
    title: str = Field(
        min_length=1,
        description="搜索结果标题",
    )
    url: str = Field(
        min_length=1,
        description="候选政策网址",
    )
    snippet: str = Field(
        default="",
        description="搜索摘要",
    )
    query: str = Field(
        min_length=1,
        description="实际执行的搜索语句",
    )
    searched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="搜索时间",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_valid(
        cls,
        value: str,
    ) -> str:
        """候选政策网址必须是 HTTP 或 HTTPS。"""
        return validate_policy_source_url(value)


def _source_domain(source: PolicySourceSlot) -> str | None:
    """取得限定搜索使用的政策源域名。"""
    if source.entry_url is None:
        return None

    return urlparse(source.entry_url).netloc


def build_policy_search_query(
    *,
    source: PolicySourceSlot,
    question: str,
    keywords: list[str],
    published_after: date | None = None,
    published_before: date | None = None,
) -> str:
    """构建限定来源或全网搜索的政策检索语句。"""
    terms: list[str] = []

    domain = _source_domain(source)

    if (
        source.kind != PolicySourceKind.OPEN_WEB
        and domain is not None
    ):
        terms.append(f"site:{domain}")

    terms.append(
        '("政策" OR "通知" OR "意见" OR "办法" '
        'OR "规划" OR "公告" OR "方案" OR "规定")'
    )

    cleaned_keywords = [
        keyword.strip()
        for keyword in keywords
        if keyword.strip()
    ]

    if cleaned_keywords:
        terms.append(" ".join(cleaned_keywords))

    cleaned_question = question.strip()

    if cleaned_question:
        terms.append(cleaned_question[:120])

    if published_after is not None:
        terms.append(
            f"after:{published_after.isoformat()}"
        )

    if published_before is not None:
        terms.append(
            f"before:{published_before.isoformat()}"
        )

    return " ".join(terms)


def parse_policy_search_results(
    *,
    payload: dict[str, object],
    source: PolicySourceSlot,
    query: str,
    max_results: int,
) -> list[PolicySearchResult]:
    """从 SerpAPI 响应中提取候选政策网页。"""
    raw_results = payload.get("organic_results")

    if not isinstance(raw_results, list):
        return []

    source_name = (
        source.name
        or "不指定来源（全网搜索）"
    )
    results: list[PolicySearchResult] = []
    seen_urls: set[str] = set()

    for fallback_position, item in enumerate(
        raw_results,
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        url = item.get("link")
        snippet = item.get("snippet", "")
        position = item.get(
            "position",
            fallback_position,
        )

        if not isinstance(title, str):
            continue

        if not isinstance(url, str):
            continue

        if url in seen_urls:
            continue

        try:
            result = PolicySearchResult(
                source_slot=source.slot,
                source_id=source.source_id,
                source_name=source_name,
                source_kind=source.kind,
                position=(
                    position
                    if isinstance(position, int)
                    else fallback_position
                ),
                title=title,
                url=url,
                snippet=(
                    snippet
                    if isinstance(snippet, str)
                    else ""
                ),
                query=query,
            )
        except ValueError:
            continue

        results.append(result)
        seen_urls.add(url)

        if len(results) >= max_results:
            break

    return results


def search_policy_candidates(
    *,
    source: PolicySourceSlot,
    question: str,
    keywords: list[str],
    published_after: date | None = None,
    published_before: date | None = None,
    max_results: int = 10,
    api_key: str | None = None,
    timeout: int = 30,
    session: requests.Session | None = None,
) -> list[PolicySearchResult]:
    """从一个已勾选来源搜索真实政策候选网页。"""
    if not source.enabled:
        raise PolicySourceSearchError(
            f"政策源选项 {source.slot} 未启用"
        )

    if max_results <= 0:
        raise PolicySourceSearchError(
            "max_results 必须大于 0"
        )

    query = build_policy_search_query(
        source=source,
        question=question,
        keywords=keywords,
        published_after=published_after,
        published_before=published_before,
    )
    active_api_key = resolve_serpapi_api_key(
        api_key=api_key,
    )
    active_session = session or requests.Session()

    try:
        response = active_session.get(
            SERPAPI_ENDPOINT,
            params={
                "engine": "google",
                "q": query,
                "api_key": active_api_key,
                "hl": "zh-cn",
                "gl": "cn",
                "num": max_results,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        raise PolicySourceSearchError(
            f"政策搜索失败：{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise PolicySourceSearchError(
            "政策搜索服务返回了无效数据"
        )

    return parse_policy_search_results(
        payload=payload,
        source=source,
        query=query,
        max_results=max_results,
    )
