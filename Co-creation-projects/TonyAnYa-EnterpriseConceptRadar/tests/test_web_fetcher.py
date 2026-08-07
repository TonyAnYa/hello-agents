"""测试真实政策网页抓取与清洗。"""

import pytest

from enterprise_concept_radar.services.web_fetcher import (
    WebFetchError,
    fetch_web_page,
)


class FakeResponse:
    """最小 requests.Response 测试替身。"""

    def __init__(
        self,
        html: str,
        *,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.url = "https://93.184.216.34/policy"
        self.status_code = 200
        self.headers = {
            "Content-Type": content_type,
        }
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self.content = html.encode("utf-8")

    def raise_for_status(self) -> None:
        """模拟成功响应。"""


class FakeSession:
    """记录网页抓取参数。"""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, url: str, **kwargs):
        assert url == "https://93.184.216.34/policy"
        assert kwargs["allow_redirects"] is True
        assert kwargs["timeout"] == 30
        return self.response


def test_fetch_web_page_extracts_article_text() -> None:
    """应优先提取政策正文容器并清除脚本。"""
    html = """
    <html>
      <head>
        <title>网页标题</title>
        <script>不应保留</script>
      </head>
      <body>
        <nav>导航内容</nav>
        <article>
          <h1>关于推进测试政策的通知</h1>
          <p>发布日期：2026年8月7日</p>
          <p>这是用于测试的正式政策正文，内容长度足够。</p>
          <p>本通知自发布之日起实施，并由有关部门负责解释。</p>
        </article>
      </body>
    </html>
    """
    page = fetch_web_page(
        "https://93.184.216.34/policy",
        session=FakeSession(
            FakeResponse(html)
        ),
        min_text_length=30,
    )

    assert page.title == "关于推进测试政策的通知"
    assert "正式政策正文" in page.text
    assert "不应保留" not in page.text
    assert page.final_url == (
        "https://93.184.216.34/policy"
    )


def test_fetch_web_page_rejects_private_address() -> None:
    """不得访问本机或内网地址。"""
    with pytest.raises(
        WebFetchError,
        match="内网",
    ):
        fetch_web_page(
            "http://127.0.0.1/private"
        )


def test_fetch_web_page_rejects_short_text() -> None:
    """正文过短时不能进入大模型分析。"""
    html = "<html><body><p>太短</p></body></html>"

    with pytest.raises(
        WebFetchError,
        match="正文过短",
    ):
        fetch_web_page(
            "https://93.184.216.34/policy",
            session=FakeSession(
                FakeResponse(html)
            ),
            min_text_length=30,
        )
