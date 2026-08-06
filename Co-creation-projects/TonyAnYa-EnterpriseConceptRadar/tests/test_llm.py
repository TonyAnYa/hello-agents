"""测试大模型配置和适配器。"""

from pathlib import Path

import pytest

from enterprise_concept_radar.services.llm import (
    LLMConfigurationError,
    LLMSettings,
    build_llm,
    invoke_connection_check,
)


def write_test_env(
    file_path: Path,
    timeout: str = "60",
) -> None:
    """创建不包含真实密钥的测试配置。"""
    file_path.write_text(
        "\n".join(
            [
                "LLM_PROVIDER=deepseek",
                "LLM_MODEL_ID=deepseek-chat",
                "LLM_API_KEY=test-secret-key",
                "LLM_BASE_URL=https://example.com",
                f"LLM_TIMEOUT={timeout}",
            ]
        ),
        encoding="utf-8",
    )


def build_test_settings() -> LLMSettings:
    """创建测试用模型配置。"""
    return LLMSettings(
        provider="deepseek",
        model_id="deepseek-chat",
        api_key="test-secret-key",
        base_url="https://example.com",
        timeout=60,
    )


def test_llm_settings_can_be_loaded(
    tmp_path: Path,
) -> None:
    """应能从环境变量文件读取模型设置。"""
    env_path = tmp_path / ".env"
    write_test_env(env_path)

    settings = LLMSettings.from_env(env_path)

    assert settings.provider == "deepseek"
    assert settings.model_id == "deepseek-chat"
    assert settings.timeout == 60


def test_api_key_is_not_in_settings_repr() -> None:
    """打印配置对象时不应泄露 API Key。"""
    settings = build_test_settings()

    assert "test-secret-key" not in repr(settings)


def test_missing_required_setting_is_rejected(
    tmp_path: Path,
) -> None:
    """缺少必要字段时应返回清晰错误。"""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LLM_MODEL_ID=deepseek-chat\n",
        encoding="utf-8",
    )

    with pytest.raises(
        LLMConfigurationError,
        match="LLM_API_KEY",
    ):
        LLMSettings.from_env(env_path)


def test_invalid_timeout_is_rejected(
    tmp_path: Path,
) -> None:
    """超时时间不是整数时应拒绝配置。"""
    env_path = tmp_path / ".env"
    write_test_env(
        env_path,
        timeout="not-a-number",
    )

    with pytest.raises(
        LLMConfigurationError,
        match="必须是整数",
    ):
        LLMSettings.from_env(env_path)


def test_build_llm_passes_expected_arguments(
    monkeypatch,
) -> None:
    """创建 HelloAgentsLLM 时应传递正确参数。"""
    captured: dict[str, object] = {}

    class FakeLLM:
        def __init__(
            self,
            **kwargs,
        ) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "enterprise_concept_radar.services.llm.HelloAgentsLLM",
        FakeLLM,
    )

    settings = build_test_settings()
    build_llm(settings)

    assert captured["provider"] == "deepseek"
    assert captured["model"] == "deepseek-chat"
    assert captured["api_key"] == "test-secret-key"
    assert captured["timeout"] == 60
    assert captured["temperature"] == 0.1


def test_connection_check_returns_clean_text(
    monkeypatch,
) -> None:
    """连通性检查应返回去除首尾空白的文本。"""

    class FakeLLM:
        def invoke(
            self,
            messages,
        ) -> str:
            assert messages[0]["role"] == "system"
            return " 连接成功 \n"

    monkeypatch.setattr(
        "enterprise_concept_radar.services.llm.build_llm",
        lambda settings: FakeLLM(),
    )

    response = invoke_connection_check(
        build_test_settings()
    )

    assert response == "连接成功"