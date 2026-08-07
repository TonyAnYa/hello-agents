"""面向客户的 Y/N 推荐设置向导。"""

from __future__ import annotations

from enterprise_concept_radar.customer_setup import (
    apply_recommended_customer_setup,
)
from enterprise_concept_radar.tracking_tasks import (
    DEFAULT_OUTPUT_DIRECTORY,
)


def ask_yes_no(
    prompt: str,
    *,
    default: bool,
) -> bool:
    """反复读取 Y/N。"""
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


def choose_output_directory() -> str:
    """默认仅需 Y/N，选择 N 时才要求填写路径。"""
    print()
    print(
        "推荐简报保存位置："
    )
    print(DEFAULT_OUTPUT_DIRECTORY)

    if ask_yes_no(
        "使用推荐保存位置吗？",
        default=True,
    ):
        return DEFAULT_OUTPUT_DIRECTORY

    while True:
        value = input(
            "请输入自定义简报目录："
        ).strip()

        if value:
            return value

        print("目录不能为空。")


def main() -> None:
    """创建客户可直接使用的推荐来源和任务。"""
    print("=" * 68)
    print("EnterpriseConceptRadar 推荐业务设置")
    print("=" * 68)
    print(
        "系统会自动启用："
        "国家能源局、国家发展改革委。"
    )
    print(
        "默认每天北京时间 08:30 和 14:00 运行。"
    )
    print(
        "以后可以在运行菜单中修改。"
    )

    enable_open_web = ask_yes_no(
        "同时启用全网搜索吗？",
        default=False,
    )
    output_directory = (
        choose_output_directory()
    )

    print()
    print("即将应用推荐设置：")
    print("- 国家能源局：启用")
    print("- 国家发展改革委：启用")
    print(
        "- 全网搜索："
        + (
            "启用"
            if enable_open_web
            else "不启用"
        )
    )
    print("- 运行时间：08:30、14:00")
    print(
        f"- 简报位置：{output_directory}"
    )

    if not ask_yes_no(
        "确认应用这些设置吗？",
        default=True,
    ):
        raise SystemExit(
            "已取消业务设置。"
        )

    result = (
        apply_recommended_customer_setup(
            output_directory=(
                output_directory
            ),
            enable_open_web=(
                enable_open_web
            ),
        )
    )

    print()
    print("推荐设置已完成。")
    print("政策来源配置：", result.source_path)
    print("追踪任务配置：", result.task_path)
    print(
        "简报保存位置：",
        result.output_directory,
    )


if __name__ == "__main__":
    main()
