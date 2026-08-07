"""面向客户的可见输入 API Key 设置向导。"""

from __future__ import annotations

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
)
from enterprise_concept_radar.secret_config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL_ID,
    DEFAULT_PROVIDER,
    DEFAULT_TIMEOUT,
    SecretConfigurationError,
    build_api_configuration,
    inspect_api_configuration,
    load_env_values,
    write_env_file_securely,
)

ENV_PATH = PROJECT_ROOT / ".env"


def ask_yes_no(
    prompt: str,
    *,
    default: bool = True,
) -> bool:
    """只接受 Y/N 的简单确认。"""
    suffix = "[Y/n]" if default else "[y/N]"

    while True:
        value = input(
            f"{prompt}{suffix} "
        ).strip().casefold()

        if not value:
            return default

        if value in {"y", "yes"}:
            return True

        if value in {"n", "no"}:
            return False

        print("请输入 Y 或 N。")


def ask_visible_secret(
    *,
    label: str,
) -> str:
    """可见输入并让用户用 Y/N 核对。"""
    while True:
        print()
        print(
            f"请输入你的 {label}。"
        )
        print(
            "输入内容会显示在屏幕上，"
            "请确认周围没有无关人员。"
        )
        value = input(
            f"{label}："
        ).strip()

        if not value:
            print(
                f"{label} 不能为空。"
            )
            continue

        print()
        print(
            f"你输入的 {label} 是："
        )
        print(value)

        if ask_yes_no(
            "确认填写正确吗？",
            default=True,
        ):
            return value

        print("请重新填写。")


def main() -> None:
    """创建或保留当前电脑的 DeepSeek/SerpAPI 配置。"""
    print("=" * 68)
    print("EnterpriseConceptRadar API 初始设置")
    print("=" * 68)
    print(
        "系统默认使用 DeepSeek 大模型和 SerpAPI 搜索。"
    )
    print(
        "本向导会显示你输入的 Key，"
        "便于当场核对。"
    )
    print(
        "Key 只保存到当前电脑的 .env，"
        "不会进入发行压缩包。"
    )
    print()

    status = inspect_api_configuration(
        ENV_PATH
    )

    if status.complete:
        print(
            "检测到当前电脑已经完成 API 配置。"
        )
        print(
            "现有 Key 不会显示，也不会被自动覆盖。"
        )

        if ask_yes_no(
            "保留当前 API 配置吗？",
            default=True,
        ):
            print("已保留当前配置。")
            return

    existing = load_env_values(
        ENV_PATH
    )
    llm_api_key = ask_visible_secret(
        label="DeepSeek API Key",
    )
    serpapi_api_key = ask_visible_secret(
        label="SerpAPI API Key",
    )

    print()
    print("即将保存以下公开配置：")
    print(
        f"- 模型提供商：{DEFAULT_PROVIDER}"
    )
    print(
        f"- 模型：{DEFAULT_MODEL_ID}"
    )
    print(
        f"- API 地址：{DEFAULT_BASE_URL}"
    )
    print(
        f"- 超时：{DEFAULT_TIMEOUT} 秒"
    )
    print(
        "- DeepSeek API Key：使用你刚才确认的内容"
    )
    print(
        "- SerpAPI API Key：使用你刚才确认的内容"
    )

    if not ask_yes_no(
        "确认保存到当前电脑吗？",
        default=True,
    ):
        raise SystemExit(
            "已取消保存，原有配置未改变。"
        )

    try:
        values = build_api_configuration(
            provider=DEFAULT_PROVIDER,
            model_id=DEFAULT_MODEL_ID,
            llm_api_key=llm_api_key,
            base_url=DEFAULT_BASE_URL,
            timeout=DEFAULT_TIMEOUT,
            serpapi_api_key=(
                serpapi_api_key
            ),
            existing_values=existing,
        )
        path = write_env_file_securely(
            env_path=ENV_PATH,
            values=values,
        )
    except SecretConfigurationError as exc:
        raise SystemExit(
            f"API 配置失败：{exc}"
        ) from exc

    print()
    print("API 配置已保存：", path)
    print(
        "以后不需要重新填写，除非主动更换 Key。"
    )


if __name__ == "__main__":
    main()
