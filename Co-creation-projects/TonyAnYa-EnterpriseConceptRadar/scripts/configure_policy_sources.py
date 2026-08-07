"""交互式配置在线政策来源。"""

from enterprise_concept_radar.agents import (
    resolve_policy_source,
)
from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.policy_sources import (
    CustomPolicySourceInput,
    PolicySourceConfigurationError,
    build_policy_source_selection,
    resolve_enabled_slots,
    save_policy_source_selection,
)
from enterprise_concept_radar.services import (
    search_policy_source_candidates,
)


def parse_slot_numbers(
    raw_value: str,
    allowed_slots: set[int],
    field_name: str,
) -> set[int]:
    """解析逗号或空格分隔的选项编号。"""
    cleaned = (
        raw_value
        .replace("，", " ")
        .replace(",", " ")
        .strip()
    )

    if not cleaned:
        return set()

    try:
        selected = {
            int(item)
            for item in cleaned.split()
        }
    except ValueError as exc:
        raise PolicySourceConfigurationError(
            f"{field_name}必须填写数字编号"
        ) from exc

    if selected - allowed_slots:
        allowed_text = "、".join(
            str(item)
            for item in sorted(allowed_slots)
        )
        raise PolicySourceConfigurationError(
            f"{field_name}只能填写：{allowed_text}"
        )

    return selected


def parse_yes_no(
    raw_value: str,
) -> bool:
    """解析是否启用全网搜索。"""
    cleaned = raw_value.strip().casefold()

    if not cleaned:
        return False

    if cleaned in {
        "y",
        "yes",
        "是",
        "1",
        "√",
    }:
        return True

    if cleaned in {
        "n",
        "no",
        "否",
        "0",
    }:
        return False

    raise PolicySourceConfigurationError(
        "全网搜索选项请输入 y 或 n"
    )


def main() -> None:
    """配置内置、自定义及全网政策来源。"""
    print("=" * 60)
    print("EnterpriseConceptRadar 政策源配置")
    print("=" * 60)
    print("[√] 选项 1：国家能源局")
    print("[√] 选项 2：国家发展改革委")
    print("[ ] 选项 3：自定义政策源")
    print("[ ] 选项 4：自定义政策源")
    print("[ ] 选项 5：自定义政策源")
    print("[ ] 选项 6：不指定来源（全网搜索）")
    print()

    disabled_builtin = parse_slot_numbers(
        raw_value=input(
            "取消勾选默认来源"
            "（1 或 2；回车表示不取消）："
        ),
        allowed_slots={
            1,
            2,
        },
        field_name="取消勾选的默认来源",
    )

    enabled_custom = parse_slot_numbers(
        raw_value=input(
            "勾选自定义来源"
            "（3、4、5；回车表示不补充）："
        ),
        allowed_slots={
            3,
            4,
            5,
        },
        field_name="自定义来源",
    )

    enable_open_web = parse_yes_no(
        input(
            "是否勾选选项 6 全网搜索？"
            "（y/N）："
        )
    )

    enabled_slots = resolve_enabled_slots(
        disabled_builtin_slots=disabled_builtin,
        enabled_custom_slots=enabled_custom,
        enable_open_web=enable_open_web,
    )

    custom_sources: list[
        CustomPolicySourceInput
    ] = []

    for slot in sorted(enabled_custom):
        print()
        print(f"[√] 配置选项 {slot}")

        requested_name = input(
            "请输入政策源名称："
        ).strip()

        print(
            f"正在搜索“{requested_name}”的官方网站候选……"
        )

        candidates = search_policy_source_candidates(
            source_name=requested_name,
        )

        print(
            "正在调用 PolicySourceResolverAgent 判断官网……"
        )

        resolution = resolve_policy_source(
            requested_name=requested_name,
            candidates=candidates,
        )

        print(
            f"匹配结果：{resolution.official_name}"
        )
        print(
            f"入口网址：{resolution.entry_url}"
        )
        print(
            f"置信度：{resolution.confidence:.2f}"
        )

        custom_sources.append(
            CustomPolicySourceInput(
                slot=slot,
                name=resolution.official_name,
                entry_url=resolution.entry_url,
            )
        )

    selection = build_policy_source_selection(
        enabled_slots=enabled_slots,
        custom_sources=custom_sources,
    )

    output_path = (
        RUNTIME_DATA_DIR
        / "config"
        / "policy_sources.json"
    )

    save_policy_source_selection(
        selection=selection,
        output_path=output_path,
    )

    print()
    print("=" * 60)
    print("政策源配置完成")
    print("=" * 60)

    for source in sorted(
        selection.slots,
        key=lambda item: item.slot,
    ):
        marker = "√" if source.enabled else " "
        print(
            f"[{marker}] 选项 {source.slot}："
            f"{source.name or '自定义政策源'}"
        )

        if source.enabled and source.entry_url:
            print(
                f"    入口网址：{source.entry_url}"
            )

    print("配置文件：", output_path)


if __name__ == "__main__":
    main()