"""为政策源解析提供搜索候选结果。"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from enterprise_concept_radar.config import PROJECT_ROOT
from enterprise_concept_radar.policy_sources import (
    PolicySourceSearchCandidate,
)


class PolicySourceSearchError(RuntimeError):
    """政策源网络搜索失败。"""
def resolve_serpapi_api_key(
    api_key: str | None = None,
) -> str:
    """取得 SerpAPI 密钥，并自动读取项目根目录的 .env。"""
    if api_key is not None and api_key.strip():
        return api_key.strip()

    load_dotenv(
        PROJECT_ROOT / ".env",
        override=False,
    )

    environment_key = os.getenv(
        "SERPAPI_API_KEY",
        "",
    ).strip()

    if not environment_key:
        raise PolicySourceSearchError(
            "缺少 SERPAPI_API_KEY，"
            "请在项目根目录的 .env 中配置"
        )

    return environment_key

def extract_search_candidates(
    payload: dict[str, object],
    max_results: int = 8,
) -> list[PolicySourceSearchCandidate]:
    """从 SerpAPI 响应中提取搜索候选结果。"""
    raw_results = payload.get("organic_results")

    if not isinstance(raw_results, list):
        return []

    candidates: list[PolicySourceSearchCandidate] = []

    for position, item in enumerate(
        raw_results,
        start=1,
    ):
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        url = item.get("link")
        snippet = item.get("snippet", "")

        if not isinstance(title, str):
            continue

        if not isinstance(url, str):
            continue

        try:
            candidate = PolicySourceSearchCandidate(
                position=position,
                title=title,
                url=url,
                snippet=(
                    snippet
                    if isinstance(snippet, str)
                    else ""
                ),
            )
        except ValueError:
            continue

        candidates.append(candidate)

        if len(candidates) >= max_results:
            break

    return candidates


def search_policy_source_candidates(
    source_name: str,
    api_key: str | None = None,
    max_results: int = 8,
    timeout: int = 20,
) -> list[PolicySourceSearchCandidate]:
    """搜索某个机构的官方网站候选结果。"""
    cleaned_name = source_name.strip()

    if not cleaned_name:
        raise PolicySourceSearchError(
            "政策源名称不能为空"
        )
    active_api_key = resolve_serpapi_api_key(
    api_key=api_key,
    )


    query = (
        f"{cleaned_name} 官方网站 "
        "政策 政府信息公开"
    )

    parameters = urlencode(
        {
            "engine": "google",
            "q": query,
            "api_key": active_api_key,
            "hl": "zh-cn",
            "gl": "cn",
            "num": max_results,
        }
    )

    request = Request(
        f"https://serpapi.com/search.json?{parameters}",
        headers={
            "User-Agent": (
                "EnterpriseConceptRadar/0.1"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=timeout,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        raise PolicySourceSearchError(
            f"搜索政策源“{cleaned_name}”失败："
            f"{type(exc).__name__}"
        ) from exc

    if not isinstance(payload, dict):
        raise PolicySourceSearchError(
            "搜索服务返回了无效数据"
        )

    candidates = extract_search_candidates(
        payload=payload,
        max_results=max_results,
    )

    if not candidates:
        raise PolicySourceSearchError(
            f"未找到政策源“{cleaned_name}”的候选网站"
        )

    return candidates