"""安全创建和更新本机 .env，不回显或记录 API Key。"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

from dotenv import dotenv_values

DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL_ID = "deepseek-chat"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_TIMEOUT = 60

REQUIRED_SECRET_NAMES = (
    "LLM_API_KEY",
    "SERPAPI_API_KEY",
)
REQUIRED_RUNTIME_NAMES = (
    "LLM_PROVIDER",
    "LLM_MODEL_ID",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_TIMEOUT",
    "SERPAPI_API_KEY",
)
PREFERRED_ENV_ORDER = (
    "LLM_PROVIDER",
    "LLM_MODEL_ID",
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_TIMEOUT",
    "SERPAPI_API_KEY",
    "GENERIC_WEBHOOK_ENDPOINT",
    "GENERIC_WEBHOOK_TOKEN",
)
PLACEHOLDER_VALUES = {
    "your-api-key",
    "your_api_key",
    "replace-me",
    "changeme",
    "sk-your-key",
}


class SecretConfigurationError(RuntimeError):
    """API 配置无效或无法安全保存。"""


@dataclass(frozen=True, slots=True)
class ApiConfigurationStatus:
    """仅包含配置状态，不包含秘密值。"""

    env_path: Path
    provider: str | None
    model_id: str | None
    base_url: str | None
    llm_key_configured: bool
    serpapi_key_configured: bool
    complete: bool


def _clean_value(
    name: str,
    value: object,
) -> str:
    """将 dotenv 值标准化为字符串。"""
    if value is None:
        return ""

    cleaned = str(value).strip()

    if "\n" in cleaned or "\r" in cleaned:
        raise SecretConfigurationError(
            f"{name} 不能包含换行符"
        )

    return cleaned


def validate_secret(
    *,
    name: str,
    value: str,
) -> str:
    """校验秘密值，不在错误信息中重复其内容。"""
    cleaned = _clean_value(
        name,
        value,
    )

    if not cleaned:
        raise SecretConfigurationError(
            f"{name} 不能为空"
        )

    if cleaned.casefold() in PLACEHOLDER_VALUES:
        raise SecretConfigurationError(
            f"{name} 仍是示例占位值"
        )

    if len(cleaned) < 8:
        raise SecretConfigurationError(
            f"{name} 长度异常，请检查是否填写完整"
        )

    return cleaned


def validate_base_url(
    value: str,
) -> str:
    """校验大模型 API 基础地址。"""
    cleaned = _clean_value(
        "LLM_BASE_URL",
        value,
    )
    parsed = urlparse(cleaned)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
        raise SecretConfigurationError(
            "LLM_BASE_URL 必须是有效的 HTTP/HTTPS 地址"
        )

    return cleaned.rstrip("/")


def validate_timeout(
    value: str | int,
) -> int:
    """校验模型超时秒数。"""
    try:
        timeout = int(value)
    except (TypeError, ValueError) as exc:
        raise SecretConfigurationError(
            "LLM_TIMEOUT 必须是整数秒数"
        ) from exc

    if not 1 <= timeout <= 600:
        raise SecretConfigurationError(
            "LLM_TIMEOUT 必须在 1 到 600 秒之间"
        )

    return timeout


def load_env_values(
    env_path: str | Path,
) -> dict[str, str]:
    """读取本机 .env；文件不存在时返回空字典。"""
    path = Path(env_path)

    if not path.is_file():
        return {}

    try:
        raw_values = dotenv_values(path)
    except OSError as exc:
        raise SecretConfigurationError(
            f"无法读取环境变量文件：{path}；{exc}"
        ) from exc

    return {
        str(name): _clean_value(
            str(name),
            value,
        )
        for name, value in raw_values.items()
        if name
    }


def build_api_configuration(
    *,
    provider: str = DEFAULT_PROVIDER,
    model_id: str = DEFAULT_MODEL_ID,
    llm_api_key: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: str | int = DEFAULT_TIMEOUT,
    serpapi_api_key: str,
    existing_values: Mapping[
        str,
        str,
    ] | None = None,
) -> dict[str, str]:
    """构建要写入 .env 的完整配置并保留其他本地变量。"""
    values = {
        str(name): _clean_value(
            str(name),
            value,
        )
        for name, value in (
            existing_values or {}
        ).items()
    }

    cleaned_provider = _clean_value(
        "LLM_PROVIDER",
        provider,
    )
    cleaned_model = _clean_value(
        "LLM_MODEL_ID",
        model_id,
    )

    if not cleaned_provider:
        raise SecretConfigurationError(
            "LLM_PROVIDER 不能为空"
        )

    if not cleaned_model:
        raise SecretConfigurationError(
            "LLM_MODEL_ID 不能为空"
        )

    values.update(
        {
            "LLM_PROVIDER": cleaned_provider,
            "LLM_MODEL_ID": cleaned_model,
            "LLM_API_KEY": validate_secret(
                name="LLM_API_KEY",
                value=llm_api_key,
            ),
            "LLM_BASE_URL": validate_base_url(
                base_url
            ),
            "LLM_TIMEOUT": str(
                validate_timeout(timeout)
            ),
            "SERPAPI_API_KEY": (
                validate_secret(
                    name="SERPAPI_API_KEY",
                    value=serpapi_api_key,
                )
            ),
        }
    )
    values.setdefault(
        "GENERIC_WEBHOOK_ENDPOINT",
        "",
    )
    values.setdefault(
        "GENERIC_WEBHOOK_TOKEN",
        "",
    )

    return values


def _quote_dotenv_value(
    value: str,
) -> str:
    """将值安全渲染为 python-dotenv 可读取的格式。"""
    if value == "":
        return ""

    if re.fullmatch(
        r"[A-Za-z0-9_./:@+\-]+",
        value,
    ):
        return value

    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )

    return f'"{escaped}"'


def render_env_file(
    values: Mapping[str, str],
) -> str:
    """以稳定顺序生成 .env 文本。"""
    normalized = {
        str(name): _clean_value(
            str(name),
            value,
        )
        for name, value in values.items()
    }
    lines = [
        "# 本文件仅保存在当前电脑，不要提交或分享。",
        "# API Key 由首次安装向导写入，程序不会回显密钥。",
        "",
        "# 大模型配置",
    ]

    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL_ID",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_TIMEOUT",
    ):
        lines.append(
            f"{name}="
            f"{_quote_dotenv_value(normalized.get(name, ''))}"
        )

    lines.extend(
        [
            "",
            "# SerpAPI 搜索配置",
            (
                "SERPAPI_API_KEY="
                + _quote_dotenv_value(
                    normalized.get(
                        "SERPAPI_API_KEY",
                        "",
                    )
                )
            ),
            "",
            "# 可选的通用 Webhook",
            (
                "GENERIC_WEBHOOK_ENDPOINT="
                + _quote_dotenv_value(
                    normalized.get(
                        "GENERIC_WEBHOOK_ENDPOINT",
                        "",
                    )
                )
            ),
            (
                "GENERIC_WEBHOOK_TOKEN="
                + _quote_dotenv_value(
                    normalized.get(
                        "GENERIC_WEBHOOK_TOKEN",
                        "",
                    )
                )
            ),
        ]
    )

    known_names = set(
        PREFERRED_ENV_ORDER
    )
    extra_names = sorted(
        name
        for name in normalized
        if name not in known_names
    )

    if extra_names:
        lines.extend(
            [
                "",
                "# 其他本地配置",
            ]
        )

        for name in extra_names:
            lines.append(
                f"{name}="
                f"{_quote_dotenv_value(normalized[name])}"
            )

    return "\n".join(lines) + "\n"


def write_env_file_securely(
    *,
    env_path: str | Path,
    values: Mapping[str, str],
) -> Path:
    """原子写入 .env，并在支持的平台限制为仅当前用户可读写。"""
    path = Path(env_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    rendered = render_env_file(
        values
    )
    temporary_path: Path | None = None

    try:
        descriptor, temporary_name = (
            tempfile.mkstemp(
                prefix=".env.",
                suffix=".tmp",
                dir=path.parent,
                text=True,
            )
        )
        temporary_path = Path(
            temporary_name
        )

        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            file.write(rendered)
            file.flush()
            os.fsync(file.fileno())

        try:
            temporary_path.chmod(0o600)
        except OSError:
            # Windows 权限语义不同，保留系统默认用户权限。
            pass

        os.replace(
            temporary_path,
            path,
        )
        temporary_path = None

        try:
            path.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        raise SecretConfigurationError(
            f"无法安全写入环境变量文件：{path}；{exc}"
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(
                missing_ok=True
            )

    return path


def inspect_api_configuration(
    env_path: str | Path,
) -> ApiConfigurationStatus:
    """只返回是否已配置，不返回 API Key。"""
    path = Path(env_path)
    values = load_env_values(path)
    llm_key = values.get(
        "LLM_API_KEY",
        "",
    )
    serpapi_key = values.get(
        "SERPAPI_API_KEY",
        "",
    )
    missing = [
        name
        for name in REQUIRED_RUNTIME_NAMES
        if not values.get(name)
    ]

    return ApiConfigurationStatus(
        env_path=path,
        provider=(
            values.get("LLM_PROVIDER")
            or None
        ),
        model_id=(
            values.get("LLM_MODEL_ID")
            or None
        ),
        base_url=(
            values.get("LLM_BASE_URL")
            or None
        ),
        llm_key_configured=bool(
            llm_key
        ),
        serpapi_key_configured=bool(
            serpapi_key
        ),
        complete=not missing,
    )
