"""按来源、主题和日期范围搜索真实政策候选网页。"""

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
POLICY_DOCUMENT_QUERY = (
    '("政策" OR "通知" OR "意见" OR "办法" '
    'OR "规划" OR "公告" OR "方案" OR "规定")'
)


class PolicySearchNoResultsError(
    PolicySourceSearchError
):
    """搜索请求成功，但搜索引擎没有返回候选结果。"""


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
        default_factory=lambda: datetime.now(
            timezone.utc
        ),
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


def _source_domain(
    source: PolicySourceSlot,
) -> str | None:
    """取得限定搜索使用的政策源域名。"""
    if source.entry_url is None:
        return None

    return urlparse(
        source.entry_url
    ).netloc


def _clean_keywords(
    keywords: list[str],
) -> list[str]:
    """去空、去重并保留关键词顺序。"""
    cleaned: list[str] = []
    seen: set[str] = set()

    for keyword in keywords:
        value = (
            keyword.strip()
            .strip('"')
            .strip("'")
        )

        if not value:
            continue

        identity = value.casefold()

        if identity in seen:
            continue

        cleaned.append(value)
        seen.add(identity)

    return cleaned


def _keyword_group(
    keywords: list[str],
) -> str | None:
    """将多个主题词改为 OR，而不是要求全部同时出现。"""
    cleaned = _clean_keywords(
        keywords
    )

    if not cleaned:
        return None

    quoted = [
        f'"{keyword}"'
        for keyword in cleaned
    ]

    return "(" + " OR ".join(quoted) + ")"


def build_policy_search_query(
    *,
    source: PolicySourceSlot,
    question: str,
    keywords: list[str],
    published_after: date | None = None,
    published_before: date | None = None,
    include_document_terms: bool = True,
) -> str:
    """构建一条不过度约束的政策搜索语句。

    日期通过 SerpAPI 的 tbs 参数传递，不写入 q。
    question 保留在签名中以兼容既有调用，但不直接
    拼入查询，避免整段自然语言把结果限制为零。
    """
    del question
    del published_after
    del published_before

    terms: list[str] = []
    domain = _source_domain(
        source
    )

    if (
        source.kind
        != PolicySourceKind.OPEN_WEB
        and domain is not None
    ):
        terms.append(
            f"site:{domain}"
        )

    if include_document_terms:
        terms.append(
            POLICY_DOCUMENT_QUERY
        )

    keyword_group = _keyword_group(
        keywords
    )

    if keyword_group is not None:
        terms.append(
            keyword_group
        )

    if not terms:
        terms.append(
            POLICY_DOCUMENT_QUERY
        )

    return " ".join(terms)


def build_policy_search_queries(
    *,
    source: PolicySourceSlot,
    question: str,
    keywords: list[str],
    published_after: date | None = None,
    published_before: date | None = None,
) -> list[str]:
    """生成最多两条由严到宽的查询，仍保持来源限制。"""
    primary = build_policy_search_query(
        source=source,
        question=question,
        keywords=keywords,
        published_after=published_after,
        published_before=published_before,
        include_document_terms=True,
    )
    broad = build_policy_search_query(
        source=source,
        question=question,
        keywords=keywords,
        published_after=published_after,
        published_before=published_before,
        include_document_terms=False,
    )

    queries: list[str] = []

    for query in (
        primary,
        broad,
    ):
        if query not in queries:
            queries.append(query)

    return queries


def build_serpapi_date_filter(
    *,
    published_after: date | None,
    published_before: date | None,
) -> str | None:
    """生成 Google 自定义日期范围 tbs 参数。"""
    if (
        published_after is None
        and published_before is None
    ):
        return None

    start = (
        published_after
        or published_before
    )
    end = (
        published_before
        or published_after
    )

    if start is None or end is None:
        return None

    if start > end:
        raise PolicySourceSearchError(
            "政策搜索开始日期不能晚于结束日期"
        )

    return (
        "cdr:1,"
        f"cd_min:{start.strftime('%m/%d/%Y')},"
        f"cd_max:{end.strftime('%m/%d/%Y')}"
    )


def parse_policy_search_results(
    *,
    payload: dict[str, object],
    source: PolicySourceSlot,
    query: str,
    max_results: int,
) -> list[PolicySearchResult]:
    """从 SerpAPI 响应中提取候选政策网页。"""
    raw_results = payload.get(
        "organic_results"
    )

    if not isinstance(
        raw_results,
        list,
    ):
        return []

    source_name = (
        source.name
        or "不指定来源（全网搜索）"
    )
    results: list[
        PolicySearchResult
    ] = []
    seen_urls: set[str] = set()

    for fallback_position, item in enumerate(
        raw_results,
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        url = item.get("link")
        snippet = item.get(
            "snippet",
            "",
        )
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
                    if isinstance(
                        position,
                        int,
                    )
                    else fallback_position
                ),
                title=title,
                url=url,
                snippet=(
                    snippet
                    if isinstance(
                        snippet,
                        str,
                    )
                    else ""
                ),
                query=query,
            )
        except ValueError:
            continue

        results.append(result)
        seen_urls.add(url)

        if (
            len(results)
            >= max_results
        ):
            break

    return results


def _serpapi_status(
    payload: dict[str, object],
) -> str | None:
    """读取 search_metadata.status。"""
    metadata = payload.get(
        "search_metadata"
    )

    if not isinstance(
        metadata,
        dict,
    ):
        return None

    status = metadata.get(
        "status"
    )

    return (
        status
        if isinstance(
            status,
            str,
        )
        else None
    )


def validate_serpapi_payload(
    payload: object,
) -> dict[str, object]:
    """检查 SerpAPI 的 JSON 状态和顶层错误。"""
    if not isinstance(
        payload,
        dict,
    ):
        raise PolicySourceSearchError(
            "政策搜索服务返回了无效数据"
        )

    status = _serpapi_status(
        payload
    )
    error = payload.get(
        "error"
    )
    error_message = (
        error.strip()
        if isinstance(
            error,
            str,
        )
        else ""
    )
    raw_results = payload.get(
        "organic_results"
    )
    has_results = (
        isinstance(
            raw_results,
            list,
        )
        and bool(raw_results)
    )

    if (
        status is not None
        and status.casefold()
        == "error"
    ):
        raise PolicySourceSearchError(
            "SerpAPI 搜索状态为 Error"
            + (
                f"：{error_message}"
                if error_message
                else ""
            )
        )

    if error_message and not has_results:
        raise PolicySearchNoResultsError(
            error_message
        )

    return payload


def _search_once(
    *,
    source: PolicySourceSlot,
    query: str,
    max_results: int,
    api_key: str,
    timeout: int,
    session: requests.Session,
    date_filter: str | None,
) -> list[PolicySearchResult]:
    """执行一次 SerpAPI 请求。"""
    parameters: dict[str, object] = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "hl": "zh-cn",
        "gl": "cn",
        "num": max_results,
    }

    if date_filter is not None:
        parameters["tbs"] = (
            date_filter
        )

    try:
        response = session.get(
            SERPAPI_ENDPOINT,
            params=parameters,
            timeout=timeout,
        )
        response.raise_for_status()
        raw_payload = response.json()
    except (
        requests.RequestException,
        ValueError,
    ) as exc:
        raise PolicySourceSearchError(
            "政策搜索失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    payload = (
        validate_serpapi_payload(
            raw_payload
        )
    )

    return parse_policy_search_results(
        payload=payload,
        source=source,
        query=query,
        max_results=max_results,
    )


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
    """从一个已勾选来源搜索真实政策候选网页。

    第一条查询包含政策文种，零结果时自动尝试
    只包含主题词的宽查询。两条查询都保留来源
    和日期范围限制，不会退化成不受控的旧网页搜索。
    """
    if not source.enabled:
        raise PolicySourceSearchError(
            f"政策源选项 {source.slot} 未启用"
        )

    if max_results <= 0:
        raise PolicySourceSearchError(
            "max_results 必须大于 0"
        )

    queries = (
        build_policy_search_queries(
            source=source,
            question=question,
            keywords=keywords,
            published_after=published_after,
            published_before=published_before,
        )
    )
    date_filter = (
        build_serpapi_date_filter(
            published_after=published_after,
            published_before=published_before,
        )
    )
    active_api_key = (
        resolve_serpapi_api_key(
            api_key=api_key,
        )
    )
    active_session = (
        session
        or requests.Session()
    )
    collected: list[
        PolicySearchResult
    ] = []
    seen_urls: set[str] = set()
    no_result_messages: list[str] = []

    for query in queries:
        try:
            results = _search_once(
                source=source,
                query=query,
                max_results=max_results,
                api_key=active_api_key,
                timeout=timeout,
                session=active_session,
                date_filter=date_filter,
            )
        except PolicySearchNoResultsError as exc:
            no_result_messages.append(
                str(exc)
            )
            continue

        for result in results:
            if result.url in seen_urls:
                continue

            collected.append(
                result
            )
            seen_urls.add(
                result.url
            )

            if (
                len(collected)
                >= max_results
            ):
                return collected

        if collected:
            return collected

    message = (
        no_result_messages[-1]
        if no_result_messages
        else "搜索引擎没有返回 organic_results"
    )

    raise PolicySearchNoResultsError(
        f"来源“{source.name or source.source_id}”"
        f"在指定日期范围内未找到候选网页；"
        f"已尝试 {len(queries)} 条查询。"
        f"搜索服务信息：{message}"
    )
