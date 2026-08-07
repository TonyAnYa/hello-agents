"""测试五项政策来源选择配置。"""

import pytest

from enterprise_concept_radar.policy_sources import (
    CustomPolicySourceInput,
    PolicySourceConfigurationError,
    build_policy_source_selection,
    load_policy_source_selection,
    resolve_enabled_slots,
    save_policy_source_selection,
)


def test_default_selection_enables_nea_and_ndrc() -> None:
    """默认配置应只启用国家能源局和国家发展改革委。"""
    selection = build_policy_source_selection()

    selected = selection.selected_sources()

    assert [
        source.slot
        for source in selected
    ] == [
        1,
        2,
    ]
    assert [
        source.source_id
        for source in selected
    ] == [
        "nea",
        "ndrc",
    ]


def test_custom_slots_are_empty_by_default() -> None:
    """选项 3、4、5 默认应为空且不启用。"""
    selection = build_policy_source_selection()

    custom_slots = [
        slot
        for slot in selection.slots
        if slot.slot in {3, 4, 5}
    ]

    assert all(
        slot.enabled is False
        for slot in custom_slots
    )
    assert all(
        slot.name is None
        for slot in custom_slots
    )
    assert all(
        slot.entry_url is None
        for slot in custom_slots
    )


def test_user_can_enable_custom_source() -> None:
    """用户填写后应能启用选项 3。"""
    selection = build_policy_source_selection(
        enabled_slots={
            1,
            2,
            3,
        },
        custom_sources=[
            CustomPolicySourceInput(
                slot=3,
                name="某省能源主管部门",
                entry_url=(
                    "https://example.gov.cn/policies/"
                ),
            ),
        ],
    )

    selected = selection.selected_sources()

    assert [
        source.slot
        for source in selected
    ] == [
        1,
        2,
        3,
    ]
    assert selected[2].name == "某省能源主管部门"


def test_selected_custom_source_requires_configuration() -> None:
    """启用自定义选项但未填写内容时应拒绝配置。"""
    with pytest.raises(
        PolicySourceConfigurationError,
        match="必须填写名称和网址",
    ):
        build_policy_source_selection(
            enabled_slots={
                1,
                2,
                3,
            },
        )


def test_at_least_one_source_is_required() -> None:
    """所有来源都关闭时应拒绝配置。"""
    with pytest.raises(
        PolicySourceConfigurationError,
        match="至少需要启用一个政策来源",
    ):
        build_policy_source_selection(
            enabled_slots=set(),
        )


def test_invalid_custom_url_is_rejected() -> None:
    """自定义政策源必须使用 HTTP 或 HTTPS 地址。"""
    with pytest.raises(
        ValueError,
        match="http 或 https",
    ):
        CustomPolicySourceInput(
            slot=3,
            name="错误来源",
            entry_url="ftp://example.gov.cn/",
        )


def test_policy_source_selection_can_round_trip_json(
    tmp_path,
) -> None:
    """政策源配置保存后应能重新读取。"""
    selection = build_policy_source_selection()
    path = save_policy_source_selection(
        selection=selection,
        output_path=tmp_path / "policy_sources.json",
    )

    restored = load_policy_source_selection(
        input_path=path,
    )

    assert [
        source.source_id
        for source in restored.selected_sources()
    ] == [
        "nea",
        "ndrc",
    ]
def test_open_web_source_can_be_enabled() -> None:
    """选项 6 应支持不指定来源的全网搜索。"""
    selection = build_policy_source_selection(
        enabled_slots={
            1,
            6,
        },
    )

    selected_slots = [
        source.slot
        for source in selection.selected_sources()
    ]

    assert selected_slots == [
        1,
        6,
    ]


def test_user_can_disable_ndrc_and_enable_custom() -> None:
    """用户可取消选项 2，并启用选项 3。"""
    enabled = resolve_enabled_slots(
        disabled_builtin_slots={
            2,
        },
        enabled_custom_slots={
            3,
        },
    )

    assert enabled == {
        1,
        3,
    }
def test_open_web_slot_has_fixed_name_and_is_disabled_by_default() -> None:
    """选项 6 应有固定名称，但默认不启用。"""
    selection = build_policy_source_selection()

    open_web = next(
        slot
        for slot in selection.slots
        if slot.slot == 6
    )

    assert open_web.name == "不指定来源（全网搜索）"
    assert open_web.entry_url is None
    assert open_web.enabled is False