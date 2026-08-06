"""HelloAgents 大模型配置与调用适配器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values
from hello_agents import HelloAgentsLLM

from enterprise_concept_radar.config import PROJECT_ROOT


class LLMConfigurationError(RuntimeError):
    """大模型配置缺失或格式错误。"""


class LLMConnectionError(RuntimeError):
    """调用大模型服务失败。"""


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """EnterpriseConceptRadar 使用的大模型配置。"""

    provider: str
    model_id: str
    api_key: str = field(repr=False)
    base_url: str
    timeout: int
    temperature: float = 0.1
    max_tokens: int = 1800

    @classmethod
    def from_env(
        cls,
        env_path: str | Path | None = None,
    ) -> "LLMSettings":
        """从项目 .env 文件读取模型配置。

        API Key 被设置为 repr=False，避免意外打印配置对象时
        将密钥暴露到终端或日志。
        """
        path = (
            Path(env_path)
            if env_path is not None
            else PROJECT_ROOT / ".env"
        )

        if not path.is_file():
            raise LLMConfigurationError(
                f"环境变量文件不存在：{path}"
            )

        values = dotenv_values(path)

        required_names = [
            "LLM_API_KEY",
            "LLM_MODEL_ID",
            "LLM_BASE_URL",
        ]
        missing_names = [
            name
            for name in required_names
            if not values.get(name)
        ]

        if missing_names:
            raise LLMConfigurationError(
                "缺少必要的大模型配置："
                + "、".join(missing_names)
            )

        timeout_text = values.get("LLM_TIMEOUT") or "60"

        try:
            timeout = int(timeout_text)
        except ValueError as exc:
            raise LLMConfigurationError(
                "LLM_TIMEOUT 必须是整数秒数"
            ) from exc

        if timeout <= 0:
            raise LLMConfigurationError(
                "LLM_TIMEOUT 必须大于 0"
            )

        return cls(
            provider=values.get("LLM_PROVIDER") or "deepseek",
            model_id=str(values["LLM_MODEL_ID"]),
            api_key=str(values["LLM_API_KEY"]),
            base_url=str(values["LLM_BASE_URL"]),
            timeout=timeout,
        )


def build_llm(
    settings: LLMSettings,
) -> HelloAgentsLLM:
    """按照项目配置创建 HelloAgentsLLM。"""
    return HelloAgentsLLM(
        model=settings.model_id,
        api_key=settings.api_key,
        base_url=settings.base_url,
        provider=settings.provider,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        timeout=settings.timeout,
    )


def invoke_connection_check(
    settings: LLMSettings | None = None,
) -> str:
    """发送一次最小请求，验证模型服务能否正常响应。"""
    active_settings = settings or LLMSettings.from_env()
    llm = build_llm(active_settings)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个 API 连通性检查程序。"
                "不要解释，只回复：连接成功"
            ),
        },
        {
            "role": "user",
            "content": "请按要求返回连通性检查结果。",
        },
    ]

    try:
        response = llm.invoke(messages)
    except Exception as exc:
        raise LLMConnectionError(
            "大模型调用失败："
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(response, str):
        raise LLMConnectionError(
            "大模型返回结果不是字符串"
        )

    cleaned_response = response.strip()

    if not cleaned_response:
        raise LLMConnectionError(
            "大模型返回了空结果"
        )

    return cleaned_response 