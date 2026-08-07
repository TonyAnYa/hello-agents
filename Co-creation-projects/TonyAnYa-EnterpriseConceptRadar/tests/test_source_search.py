"""测试政策源网络搜索服务。"""

from enterprise_concept_radar.services import (
    source_search,
)


def test_resolve_serpapi_key_prefers_explicit_value() -> None:
    """显式传入的密钥应优先使用。"""
    result = source_search.resolve_serpapi_api_key(
        api_key=" test-api-key ",
    )

    assert result == "test-api-key"


def test_resolve_serpapi_key_loads_project_environment(
    monkeypatch,
) -> None:
    """未显式传入时应加载项目 .env。"""
    monkeypatch.delenv(
        "SERPAPI_API_KEY",
        raising=False,
    )

    def fake_load_dotenv(
        path,
        override=False,
    ) -> bool:
        assert path == source_search.PROJECT_ROOT / ".env"
        assert override is False
        monkeypatch.setenv(
            "SERPAPI_API_KEY",
            "environment-test-key",
        )
        return True

    monkeypatch.setattr(
        source_search,
        "load_dotenv",
        fake_load_dotenv,
    )

    result = source_search.resolve_serpapi_api_key()

    assert result == "environment-test-key"
    