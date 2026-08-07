"""安全下载并清洗真实政策网页。"""

from __future__ import annotations

import codecs
import ipaddress
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; EnterpriseConceptRadar/0.1; "
    "+https://github.com/TonyAnYa/hello-agents)"
)
SUPPORTED_CONTENT_TYPES = {
    "text/html",
    "application/xhtml+xml",
    "text/plain",
}
HTML_CHARSET_PATTERN = re.compile(
    rb"charset\s*=\s*[\"']?\s*"
    rb"([a-zA-Z0-9._:-]+)",
    flags=re.IGNORECASE,
)
MOJIBAKE_MARKERS = (
    "Ã",
    "Â",
    "â€",
    "æ",
    "ç",
    "å",
    "é",
    "è",
    "ï¼",
    "ã€",
)


class WebFetchError(RuntimeError):
    """网页地址不安全、网络请求失败或正文无法提取。"""


def validate_public_http_url(value: str) -> str:
    """校验 URL，并阻止本机、内网及保留地址。"""
    cleaned = value.strip()
    parsed = urlparse(cleaned)

    if parsed.scheme not in {"http", "https"}:
        raise WebFetchError("网页地址必须使用 http 或 https")

    if not parsed.hostname:
        raise WebFetchError("网页地址缺少有效主机名")

    if parsed.username or parsed.password:
        raise WebFetchError("网页地址不能包含用户名或密码")

    hostname = parsed.hostname.casefold()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise WebFetchError("不允许访问本机地址")

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return cleaned

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise WebFetchError("不允许访问内网、本机或保留地址")

    return cleaned


def _normalize_encoding_name(
    value: str | None,
) -> str | None:
    """将编码别名转换为 Python 标准名称。"""
    if value is None:
        return None

    cleaned = value.strip().strip('"').strip("'")

    if not cleaned:
        return None

    try:
        return codecs.lookup(cleaned).name
    except LookupError:
        return None


def _header_charset(
    raw_content_type: str,
) -> str | None:
    """只读取 HTTP 头明确声明的 charset。"""
    match = re.search(
        r"charset\s*=\s*[\"']?"
        r"([^;\"'\s]+)",
        raw_content_type,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return _normalize_encoding_name(
        match.group(1)
    )


def _bom_encoding(
    raw_content: bytes,
) -> str | None:
    """根据 Unicode BOM 识别编码。"""
    signatures = (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    )

    for signature, encoding in signatures:
        if raw_content.startswith(signature):
            return encoding

    return None


def _html_charset(
    raw_content: bytes,
) -> str | None:
    """从 HTML 前部的 meta charset 中读取编码。"""
    match = HTML_CHARSET_PATTERN.search(
        raw_content[:32_768]
    )

    if match is None:
        return None

    try:
        value = match.group(1).decode(
            "ascii"
        )
    except UnicodeDecodeError:
        return None

    return _normalize_encoding_name(value)


def _decoded_text_quality(
    text: str,
) -> float:
    """给解码结果评分，降低替换符和乱码的权重。"""
    if not text:
        return float("-inf")

    replacement_count = text.count("\ufffd")
    control_count = sum(
        1
        for character in text
        if ord(character) < 32
        and character not in "\n\r\t"
    )
    cjk_count = sum(
        1
        for character in text
        if (
            "\u3400" <= character <= "\u4dbf"
            or "\u4e00" <= character <= "\u9fff"
        )
    )
    mojibake_count = sum(
        text.count(marker)
        for marker in MOJIBAKE_MARKERS
    )
    printable_count = sum(
        1
        for character in text
        if character.isprintable()
        or character in "\n\r\t"
    )
    printable_ratio = (
        printable_count / len(text)
    )

    return (
        cjk_count * 3.0
        + printable_ratio * 100.0
        - replacement_count * 120.0
        - control_count * 20.0
        - mojibake_count * 9.0
    )


def decode_web_content(
    *,
    raw_content: bytes,
    raw_content_type: str,
    apparent_encoding: str | None,
) -> tuple[str, str]:
    """从多个可靠信号中选择质量最高的网页解码。"""
    candidates: list[
        tuple[str, float]
    ] = []

    def add_candidate(
        value: str | None,
        bias: float,
    ) -> None:
        normalized = (
            _normalize_encoding_name(value)
        )

        if normalized is None:
            return

        if any(
            existing == normalized
            for existing, _ in candidates
        ):
            return

        candidates.append(
            (normalized, bias)
        )

    add_candidate(
        _bom_encoding(raw_content),
        30.0,
    )
    add_candidate(
        _header_charset(
            raw_content_type
        ),
        20.0,
    )
    add_candidate(
        _html_charset(raw_content),
        18.0,
    )
    add_candidate(
        apparent_encoding,
        8.0,
    )
    add_candidate("utf-8", 4.0)
    add_candidate("gb18030", 2.0)

    best_text: str | None = None
    best_encoding: str | None = None
    best_score = float("-inf")

    for encoding, bias in candidates:
        try:
            decoded = raw_content.decode(
                encoding,
                errors="strict",
            )
        except UnicodeDecodeError:
            continue

        score = (
            _decoded_text_quality(decoded)
            + bias
        )

        if score > best_score:
            best_text = decoded
            best_encoding = encoding
            best_score = score

    if (
        best_text is None
        or best_encoding is None
    ):
        best_encoding = "utf-8"
        best_text = raw_content.decode(
            best_encoding,
            errors="replace",
        )

    return best_text, best_encoding


def normalize_page_text(value: str) -> str:
    """清理网页文本，同时保留适合后续 LLM 分析的段落结构。"""
    normalized_lines: list[str] = []

    for raw_line in value.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()

        if line:
            normalized_lines.append(line)

    return "\n".join(normalized_lines)


def _extract_page_title(soup: BeautifulSoup) -> str:
    """优先读取正文标题，其次使用 HTML title。"""
    heading = soup.find("h1")

    if heading is not None:
        heading_text = normalize_page_text(
            heading.get_text(" ", strip=True)
        )

        if heading_text:
            return heading_text

    if soup.title is not None:
        return normalize_page_text(
            soup.title.get_text(" ", strip=True)
        )

    return "未识别网页标题"


def _select_content_root(soup: BeautifulSoup):
    """选择政府网站常见的正文容器。"""
    selectors = (
        "#UCAP-CONTENT",
        "[id*='UCAP-CONTENT']",
        ".TRS_Editor",
        ".article-content",
        ".article_content",
        ".article",
        ".zwxl",
        ".content",
        "article",
        "main",
    )

    for selector in selectors:
        node = soup.select_one(selector)

        if node is not None:
            text = normalize_page_text(
                node.get_text("\n", strip=True)
            )

            if len(text) >= 80:
                return node

    return soup.body or soup


class FetchedWebPage(BaseModel):
    """经过下载和正文清洗的真实网页。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    requested_url: str = Field(
        min_length=1,
        description="最初请求的网址",
    )
    final_url: str = Field(
        min_length=1,
        description="完成重定向后的最终网址",
    )
    status_code: int = Field(
        ge=100,
        le=599,
        description="HTTP 状态码",
    )
    content_type: str = Field(
        min_length=1,
        description="响应内容类型",
    )
    encoding: str = Field(
        default="unknown",
        min_length=1,
        description="网页正文最终采用的字符编码",
    )
    title: str = Field(
        min_length=1,
        description="网页标题",
    )
    text: str = Field(
        min_length=20,
        description="经过清洗的网页正文",
    )
    html: str = Field(
        min_length=1,
        description="原始 HTML 或纯文本快照",
    )
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="抓取时间",
    )

    @field_validator(
        "requested_url",
        "final_url",
    )
    @classmethod
    def urls_must_be_public_http(
        cls,
        value: str,
    ) -> str:
        """保存前再次校验原始和最终地址。"""
        return validate_public_http_url(value)


def fetch_web_page(
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: int = 30,
    max_bytes: int = 5_000_000,
    min_text_length: int = 80,
) -> FetchedWebPage:
    """下载网页并提取政策正文。

    网络失败、非文本响应、超大页面或正文过短时直接报错，
    不会回退到模拟数据。
    """
    requested_url = validate_public_http_url(url)
    active_session = session or requests.Session()

    try:
        response = active_session.get(
            requested_url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "text/plain;q=0.9,*/*;q=0.1"
                ),
            },
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WebFetchError(
            f"网页抓取失败：{type(exc).__name__}: {exc}"
        ) from exc

    final_url = validate_public_http_url(
        str(response.url)
    )
    raw_content = response.content

    if len(raw_content) > max_bytes:
        raise WebFetchError(
            f"网页内容超过大小限制：{len(raw_content)} 字节"
        )

    raw_content_type = response.headers.get(
        "Content-Type",
        "",
    )
    content_type = (
        raw_content_type.split(";", 1)[0]
        .strip()
        .casefold()
    )

    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise WebFetchError(
            "当前仅支持 HTML 或纯文本网页，"
            f"实际类型：{content_type or '未知'}"
        )

    html, detected_encoding = (
        decode_web_content(
            raw_content=raw_content,
            raw_content_type=(
                raw_content_type
            ),
            apparent_encoding=(
                response.apparent_encoding
            ),
        )
    )

    if content_type == "text/plain":
        title = "纯文本政策页面"
        text = normalize_page_text(html)
    else:
        soup = BeautifulSoup(html, "html.parser")

        for tag_name in (
            "script",
            "style",
            "noscript",
            "svg",
            "iframe",
            "form",
            "nav",
            "footer",
        ):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        title = _extract_page_title(soup)
        content_root = _select_content_root(soup)
        text = normalize_page_text(
            content_root.get_text("\n", strip=True)
        )

    if len(text) < min_text_length:
        raise WebFetchError(
            "网页正文过短，无法作为政策材料："
            f"{len(text)} 字符"
        )

    return FetchedWebPage(
        requested_url=requested_url,
        final_url=final_url,
        status_code=response.status_code,
        content_type=content_type,
        encoding=detected_encoding,
        title=title,
        text=text,
        html=html,
    )
