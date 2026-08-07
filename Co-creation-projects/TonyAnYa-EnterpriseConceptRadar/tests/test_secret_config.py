"""测试 API Key 本地安全配置。"""

import os

import pytest
from dotenv import dotenv_values

from enterprise_concept_radar.secret_config import (
    SecretConfigurationError,
    build_api_configuration,
    inspect_api_configuration,
    render_env_file,
    write_env_file_securely,
)


def build_values():
    """创建仅用于测试的虚构 Key。"""
    return build_api_configuration(
        provider="deepseek",
        model_id="deepseek-chat",
        llm_api_key=(
            "test-deepseek-key-123456"
        ),
        base_url=(
            "https://api.deepseek.com"
        ),
        timeout=60,
        serpapi_api_key=(
            "test-serpapi-key-654321"
        ),
    )


def test_env_template_contains_keys_once() -> None:
    """渲染内容应完整但不重复字段。"""
    rendered = render_env_file(
        build_values()
    )

    assert rendered.count(
        "LLM_API_KEY="
    ) == 1
    assert rendered.count(
        "SERPAPI_API_KEY="
    ) == 1
    assert "test-deepseek-key-123456" in rendered


def test_secure_write_and_status(
    tmp_path,
) -> None:
    """保存后可读取状态，但状态对象不包含密钥字段。"""
    path = write_env_file_securely(
        env_path=tmp_path / ".env",
        values=build_values(),
    )
    values = dotenv_values(path)
    status = inspect_api_configuration(
        path
    )

    assert values["LLM_API_KEY"] == (
        "test-deepseek-key-123456"
    )
    assert status.complete is True
    assert status.llm_key_configured is True
    assert (
        not hasattr(
            status,
            "llm_api_key",
        )
    )

    if os.name != "nt":
        assert (
            path.stat().st_mode & 0o777
        ) == 0o600


def test_existing_optional_values_are_preserved() -> None:
    """重新配置时应保留其他本地变量。"""
    values = build_api_configuration(
        provider="deepseek",
        model_id="deepseek-chat",
        llm_api_key=(
            "test-deepseek-key-123456"
        ),
        base_url=(
            "https://api.deepseek.com"
        ),
        timeout=60,
        serpapi_api_key=(
            "test-serpapi-key-654321"
        ),
        existing_values={
            "GENERIC_WEBHOOK_ENDPOINT": (
                "https://example.com/hook"
            ),
            "CUSTOM_SETTING": "local-only",
        },
    )

    assert values[
        "GENERIC_WEBHOOK_ENDPOINT"
    ] == "https://example.com/hook"
    assert values["CUSTOM_SETTING"] == (
        "local-only"
    )


def test_placeholder_secret_is_rejected() -> None:
    """示例占位值不能被当作正式 Key。"""
    with pytest.raises(
        SecretConfigurationError,
        match="占位",
    ):
        build_api_configuration(
            llm_api_key="your-api-key",
            serpapi_api_key=(
                "test-serpapi-key-654321"
            ),
        )


def test_invalid_base_url_is_rejected() -> None:
    """模型地址必须是 HTTP/HTTPS URL。"""
    with pytest.raises(
        SecretConfigurationError,
        match="HTTP/HTTPS",
    ):
        build_api_configuration(
            llm_api_key=(
                "test-deepseek-key-123456"
            ),
            base_url="not-a-url",
            serpapi_api_key=(
                "test-serpapi-key-654321"
            ),
        )
