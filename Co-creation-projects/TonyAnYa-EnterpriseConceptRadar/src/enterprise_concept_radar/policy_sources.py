"""政策来源选择、校验与持久化配置。"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

NEA_SOURCE_URL = "https://www.nea.gov.cn/"
NDRC_SOURCE_URL = "https://www.ndrc.gov.cn/"


class PolicySourceConfigurationError(RuntimeError):
    """政策来源配置无效或无法读取。"""



class PolicySourceKind(str, Enum):
    """政策来源类型。"""

    BUILTIN = "内置政策源"
    CUSTOM = "自定义政策源"
    OPEN_WEB = "全网搜索"

def validate_policy_source_url(
    value: str,
) -> str:
    """校验政策源入口必须是 HTTP 或 HTTPS URL。"""
    cleaned_value = value.strip()
    parsed = urlparse(cleaned_value)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "政策源网址必须使用 http 或 https"
        )

    if not parsed.netloc:
        raise ValueError(
            "政策源网址缺少有效域名"
        )

    return cleaned_value

class PolicySourceSearchCandidate(BaseModel):
    """搜索引擎返回的一个政策源候选网站。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    position: int = Field(
        ge=1,
        description="搜索结果位置",
    )
    title: str = Field(
        min_length=1,
        description="搜索结果标题",
    )
    url: str = Field(
        min_length=1,
        description="候选网站地址",
    )
    snippet: str = Field(
        default="",
        description="搜索摘要",
    )

    @field_validator("url")
    @classmethod
    def candidate_url_must_be_valid(
        cls,
        value: str,
    ) -> str:
        """候选网址必须是 HTTP 或 HTTPS 地址。"""
        return validate_policy_source_url(value)


class PolicySourceResolverDecision(BaseModel):
    """LLM 对搜索候选结果作出的选择。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    official_name: str = Field(
        min_length=1,
        description="机构的正式名称",
    )
    selected_candidate_index: int = Field(
        ge=0,
        description="选中的候选结果索引，从 0 开始",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="来源匹配置信度",
    )
    reason: str = Field(
        min_length=1,
        description="选择该候选网站的理由",
    )


class PolicySourceResolution(BaseModel):
    """搜索和 LLM 判断后的政策源解析结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    requested_name: str = Field(
        min_length=1,
        description="用户输入的机构名称",
    )
    official_name: str = Field(
        min_length=1,
        description="LLM 判断的正式机构名称",
    )
    entry_url: str = Field(
        min_length=1,
        description="从搜索候选中选出的官网地址",
    )
    source_domain: str = Field(
        min_length=1,
        description="官网域名",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="来源匹配置信度",
    )
    reason: str = Field(
        min_length=1,
        description="来源匹配理由",
    )

class CustomPolicySourceInput(BaseModel):
    """用户填写的一个自定义政策来源。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    slot: int = Field(
        ge=3,
        le=5,
        description="自定义来源所在选项，只能是 3、4 或 5",
    )
    name: str = Field(
        min_length=1,
        max_length=100,
        description="自定义政策源名称",
    )
    entry_url: str = Field(
        min_length=1,
        description="自定义政策源入口网址",
    )

    @field_validator("entry_url")
    @classmethod
    def entry_url_must_be_valid(
        cls,
        value: str,
    ) -> str:
        """自定义入口必须是有效网页地址。"""
        return validate_policy_source_url(value)


class PolicySourceSlot(BaseModel):
    """用户界面中的一个政策源选项。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    slot: int = Field(
        ge=1,
        le=6,
        description="选项编号",
    )
    source_id: str = Field(
        min_length=1,
        description="政策源内部标识",
    )
    kind: PolicySourceKind = Field(
        description="内置来源或自定义来源",
    )
    name: str | None = Field(
        default=None,
        description="政策源显示名称",
    )
    entry_url: str | None = Field(
        default=None,
        description="政策源入口网址",
    )
    enabled: bool = Field(
        default=False,
        description="本次执行是否启用",
    )

    @field_validator(
        "name",
        "entry_url",
        mode="before",
    )
    @classmethod
    def blank_value_becomes_none(
        cls,
        value: object,
    ) -> object:
        """将空字符串统一转换为 None。"""
        if isinstance(value, str) and not value.strip():
            return None

        return value

    @field_validator("entry_url")
    @classmethod
    def optional_entry_url_must_be_valid(
        cls,
        value: str | None,
    ) -> str | None:
        """已填写的入口网址必须合法。"""
        if value is None:
            return None

        return validate_policy_source_url(value)

    @model_validator(mode="after")
    def validate_slot_definition(
        self,
    ) -> "PolicySourceSlot":
        """校验内置和自定义来源的选项范围。"""
        if self.kind == PolicySourceKind.BUILTIN:
            if self.slot not in {
                1,
                2,
            }:
                raise ValueError(
                    "内置政策源只能使用选项 1 或 2"
                )

            if self.name is None or self.entry_url is None:
                raise ValueError(
                    "内置政策源必须包含名称和网址"
                )

        if self.kind == PolicySourceKind.CUSTOM:
            if self.slot not in {
                3,
                4,
                5,
            }:
                raise ValueError(
                    "自定义政策源只能使用选项 3、4 或 5"
                )

            has_name = self.name is not None
            has_url = self.entry_url is not None

            if has_name != has_url:
                raise ValueError(
                    "自定义政策源必须同时填写名称和网址"
                )

            if self.enabled and not (
                has_name and has_url
            ):
                raise ValueError(
                    "启用的自定义政策源必须填写名称和网址"
                )

        if self.kind == PolicySourceKind.OPEN_WEB:
            if self.slot != 6:
                raise ValueError(
                    "全网搜索只能使用选项 6"
                )

            if self.name is None:
                raise ValueError(
                    "全网搜索选项必须包含显示名称"
                )

            if self.entry_url is not None:
                raise ValueError(
                    "全网搜索选项不能设置固定入口网址"
                )

        return self


class PolicySourceSelection(BaseModel):
    """一次在线运行使用的五项政策源配置。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    slots: list[PolicySourceSlot] = Field(
        min_length=6,
        max_length=6,
        description="固定的六个政策源选项",
    )

    @model_validator(mode="after")
    def validate_complete_selection(
        self,
    ) -> "PolicySourceSelection":
        """校验五个选项、默认来源和启用状态。"""
        slots_by_number = {
            slot.slot: slot
            for slot in self.slots
        }

        if set(slots_by_number) != {
            1,
            2,
            3,
            4,
            5,
            6,
        }:
            raise ValueError(
                "政策源配置必须完整包含选项 1 到 5"
            )

        source_ids = [
            slot.source_id
            for slot in self.slots
        ]

        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                "政策源 source_id 不能重复"
            )

        source_1 = slots_by_number[1]
        source_2 = slots_by_number[2]
        source_6 = slots_by_number[6]

        if (
            source_6.source_id != "open-web"
            or source_6.name != "不指定来源（全网搜索）"
            or source_6.entry_url is not None
            or source_6.kind != PolicySourceKind.OPEN_WEB
        ):
            raise ValueError(
                "选项 6 必须是不指定来源的全网搜索"
            )


        if (
            source_1.source_id != "nea"
            or source_1.name != "国家能源局"
            or source_1.entry_url != NEA_SOURCE_URL
            or source_1.kind
            != PolicySourceKind.BUILTIN
        ):
            raise ValueError(
                "选项 1 必须是国家能源局内置政策源"
            )

        if (
            source_2.source_id != "ndrc"
            or source_2.name != "国家发展改革委"
            or source_2.entry_url != NDRC_SOURCE_URL
            or source_2.kind
            != PolicySourceKind.BUILTIN
        ):
            raise ValueError(
                "选项 2 必须是国家发展改革委内置政策源"
            )

        if not any(
            slot.enabled
            for slot in self.slots
        ):
            raise ValueError(
                "至少需要启用一个政策来源"
            )

        return self

    def selected_sources(
        self,
    ) -> list[PolicySourceSlot]:
        """按照选项顺序返回本次启用的政策源。"""
        return sorted(
            (
                slot
                for slot in self.slots
                if slot.enabled
            ),
            key=lambda slot: slot.slot,
        )

    def resolve_enabled_slots(
        disabled_builtin_slots: Iterable[int] = (),
        enabled_custom_slots: Iterable[int] = (),
        enable_open_web: bool = False,
    ) -> set[int]:
        """计算用户交互后的最终勾选项。"""
        disabled_builtin = set(disabled_builtin_slots)
        enabled_custom = set(enabled_custom_slots)

        invalid_disabled = disabled_builtin - {
            1,
            2,
        }

        if invalid_disabled:
            raise PolicySourceConfigurationError(
                "只能取消默认政策源选项 1 或 2"
            )

        invalid_custom = enabled_custom - {
            3,
            4,
            5,
        }

        if invalid_custom:
            raise PolicySourceConfigurationError(
                "自定义政策源只能选择 3、4、5"
            )

        enabled = (
            {
                1,
                2,
            }
            - disabled_builtin
        ) | enabled_custom

        if enable_open_web:
            enabled.add(6)

        if not enabled:
            raise PolicySourceConfigurationError(
                "至少需要勾选一个政策来源"
            )

        return enabled

def resolve_enabled_slots(
    disabled_builtin_slots: Iterable[int] = (),
    enabled_custom_slots: Iterable[int] = (),
    enable_open_web: bool = False,
) -> set[int]:
    """计算用户交互后的最终勾选项。

    选项 1、2 默认勾选，但可以取消。
    选项 3、4、5 默认不勾选，可以主动启用。
    选项 6 表示不指定来源的全网搜索。
    """
    disabled_builtin = set(
        disabled_builtin_slots
    )
    enabled_custom = set(
        enabled_custom_slots
    )

    invalid_disabled = disabled_builtin - {
        1,
        2,
    }

    if invalid_disabled:
        raise PolicySourceConfigurationError(
            "只能取消默认政策源选项 1 或 2"
        )

    invalid_custom = enabled_custom - {
        3,
        4,
        5,
    }

    if invalid_custom:
        raise PolicySourceConfigurationError(
            "自定义政策源只能选择 3、4、5"
        )

    enabled = (
        {
            1,
            2,
        }
        - disabled_builtin
    ) | enabled_custom

    if enable_open_web:
        enabled.add(6)

    if not enabled:
        raise PolicySourceConfigurationError(
            "至少需要启用一个政策来源"
        )

    return enabled
def build_policy_source_selection(
    enabled_slots: Iterable[int] | None = None,
    custom_sources: Iterable[
        CustomPolicySourceInput
    ] = (),
) -> PolicySourceSelection:
    """创建政策源选择配置。

    enabled_slots 未传入时，默认启用选项 1 和 2。
    """
    enabled = (
        {
            1,
            2,
        }
        if enabled_slots is None
        else set(enabled_slots)
    )

    invalid_slots = enabled - {
        1,
        2,
        3,
        4,
        5,
        6,
    }

    if invalid_slots:
        invalid_text = "、".join(
            str(slot)
            for slot in sorted(invalid_slots)
        )
        raise PolicySourceConfigurationError(
            f"存在无效政策源选项：{invalid_text}"
        )

    custom_by_slot: dict[
        int,
        CustomPolicySourceInput,
    ] = {}

    for source in custom_sources:
        if source.slot in custom_by_slot:
            raise PolicySourceConfigurationError(
                f"自定义政策源选项 {source.slot} 重复"
            )

        custom_by_slot[source.slot] = source

    missing_custom_slots = sorted(
        slot
        for slot in enabled
        if (
            slot in {
                3,
                4,
                5,
            }
            and slot not in custom_by_slot
        )
    )

    if missing_custom_slots:
        missing_text = "、".join(
            str(slot)
            for slot in missing_custom_slots
        )

        raise PolicySourceConfigurationError(
            "启用的自定义政策源选项 "
            f"{missing_text} 必须填写名称和网址"
        )

    slots = [
        PolicySourceSlot(
            slot=1,
            source_id="nea",
            kind=PolicySourceKind.BUILTIN,
            name="国家能源局",
            entry_url=NEA_SOURCE_URL,
            enabled=1 in enabled,
        ),
        PolicySourceSlot(
            slot=2,
            source_id="ndrc",
            kind=PolicySourceKind.BUILTIN,
            name="国家发展改革委",
            entry_url=NDRC_SOURCE_URL,
            enabled=2 in enabled,
        ),
    ]

    for slot_number in (
        3,
        4,
        5,
    ):
        custom = custom_by_slot.get(
            slot_number
        )

        slots.append(
            PolicySourceSlot(
                slot=slot_number,
                source_id=f"custom-{slot_number}",
                kind=PolicySourceKind.CUSTOM,
                name=(
                    custom.name
                    if custom is not None
                    else None
                ),
                entry_url=(
                    custom.entry_url
                    if custom is not None
                    else None
                ),
                enabled=slot_number in enabled,
            )
        )

    # 选项 6 只能添加一次，因此必须位于循环外。
    slots.append(
        PolicySourceSlot(
            slot=6,
            source_id="open-web",
            kind=PolicySourceKind.OPEN_WEB,
            name="不指定来源（全网搜索）",
            entry_url=None,
            enabled=6 in enabled,
        )
    )
    

    try:
        return PolicySourceSelection(
            slots=slots,
        )
    except ValidationError as exc:
        raise PolicySourceConfigurationError(
            f"政策源配置无效：\n{exc}"
        ) from exc


def save_policy_source_selection(
    selection: PolicySourceSelection,
    output_path: str | Path,
) -> Path:
    """保存政策源选择配置。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        selection.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    return path


def load_policy_source_selection(
    input_path: str | Path,
) -> PolicySourceSelection:
    """读取并校验政策源选择配置。"""
    path = Path(input_path)

    if not path.is_file():
        raise PolicySourceConfigurationError(
            f"政策源配置文件不存在：{path}"
        )

    try:
        return PolicySourceSelection.model_validate_json(
            path.read_text(
                encoding="utf-8",
            )
        )
    except OSError as exc:
        raise PolicySourceConfigurationError(
            f"无法读取政策源配置：{path}；{exc}"
        ) from exc
    except ValidationError as exc:
        raise PolicySourceConfigurationError(
            f"政策源配置文件无效：{path}；{exc}"
        ) from exc