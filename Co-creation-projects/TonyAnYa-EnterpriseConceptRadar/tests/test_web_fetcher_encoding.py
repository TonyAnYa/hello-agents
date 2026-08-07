"""测试政府网页字符编码识别。"""

from enterprise_concept_radar.services.web_fetcher import (
    fetch_web_page,
)

URL = "https://93.184.216.34/policy"


class BytesResponse:
    """允许独立设置原始字节和 Requests 推断编码。"""

    def __init__(
        self,
        content: bytes,
        *,
        content_type: str,
        response_encoding: str | None,
        apparent_encoding: str | None,
    ) -> None:
        self.url = URL
        self.status_code = 200
        self.headers = {
            "Content-Type": content_type,
        }
        self.encoding = response_encoding
        self.apparent_encoding = apparent_encoding
        self.content = content

    def raise_for_status(self) -> None:
        """模拟成功响应。"""


class BytesSession:
    """返回指定字节响应。"""

    def __init__(
        self,
        response: BytesResponse,
    ) -> None:
        self.response = response

    def get(
        self,
        url: str,
        **kwargs,
    ) -> BytesResponse:
        assert url == URL
        return self.response


def test_missing_header_does_not_trust_latin1_default() -> None:
    """无 charset 时不能优先采用 Requests 的 latin1。"""
    html = """
    <html><body><article>
    <h1>关于推进新能源项目的通知</h1>
    <p>这是完整的中文政策正文，包含发布日期和实施要求。</p>
    <p>各有关单位应当认真组织实施并及时反馈情况。</p>
    </article></body></html>
    """.encode("utf-8")
    response = BytesResponse(
        html,
        content_type="text/html",
        response_encoding="ISO-8859-1",
        apparent_encoding="utf-8",
    )

    page = fetch_web_page(
        URL,
        session=BytesSession(response),
        min_text_length=30,
    )

    assert "新能源项目" in page.text
    assert "æ–°" not in page.text
    assert page.encoding == "utf-8"


def test_html_meta_gb18030_is_respected() -> None:
    """中文政府网站 meta 声明 GB18030 时应正确解码。"""
    html = """
    <html>
      <head><meta charset="gb18030"></head>
      <body><article>
        <h1>电力安全生产行动计划</h1>
        <p>本行动计划明确电网安全治理目标和重点任务。</p>
        <p>各单位应当持续提高应急管理和风险防控能力。</p>
      </article></body>
    </html>
    """.encode("gb18030")
    response = BytesResponse(
        html,
        content_type="text/html",
        response_encoding="ISO-8859-1",
        apparent_encoding=None,
    )

    page = fetch_web_page(
        URL,
        session=BytesSession(response),
        min_text_length=30,
    )

    assert "电力安全生产行动计划" in page.text
    assert page.encoding == "gb18030"
