"""政策追踪任务、运行状态和投递目标配置。"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

DEFAULT_SOURCE_CONFIG_PATH = (
    "data/runtime/config/policy_sources.json"
)
DEFAULT_OUTPUT_DIRECTORY = (
    "~/Documents/EnterpriseConceptRadarReports"
)
TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
SCHEDULE_TIME_PATTERN = re.compile(
    r"^(?:[01]\d|2[0-3]):[0-5]\d$"
)


class TrackingTaskError(RuntimeError):
    """追踪任务配置读取、保存或校验失败。"""


class DateRangeMode(str, Enum):
    """政策搜索时间范围计算模式。"""

    SINCE_LAST_SUCCESS = "自上次成功运行"
    ROLLING_DAYS = "滚动天数"


class DeliveryChannel(str, Enum):
    """统一投递渠道类型。"""

    LOCAL = "local"
    EMAIL = "email"
    GENERIC_WEBHOOK = "generic_webhook"
    WECOM = "wecom"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    ENTERPRISE_BRAIN = "enterprise_brain"


class DateRangeConfig(BaseModel):
    """一次任务的政策搜索时间范围规则。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    mode: DateRangeMode = Field(
        default=DateRangeMode.SINCE_LAST_SUCCESS,
        description="时间范围计算模式",
    )
    initial_lookback_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="首次运行向前检索的天数",
    )
    overlap_hours: int = Field(
        default=36,
        ge=0,
        le=168,
        description="从上次成功时间向前重叠的小时数",
    )
    rolling_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="滚动时间范围天数",
    )


class TrackingSchedule(BaseModel):
    """每日多时间点调度配置。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    enabled: bool = Field(
        default=True,
        description="是否启用定时运行",
    )
    timezone: str = Field(
        default="Asia/Shanghai",
        min_length=1,
        description="IANA 时区名称",
    )
    times: list[str] = Field(
        default_factory=lambda: [
            "08:30",
            "14:00",
        ],
        min_length=1,
        max_length=24,
        description="每日执行时间，格式 HH:MM",
    )
    catch_up_minutes: int = Field(
        default=90,
        ge=0,
        le=720,
        description="调度进程晚启动后的补跑窗口",
    )

    @field_validator("timezone")
    @classmethod
    def timezone_must_exist(
        cls,
        value: str,
    ) -> str:
        """时区必须能被 Python zoneinfo 识别。"""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(
                f"无法识别时区：{value}"
            ) from exc

        return value

    @field_validator("times")
    @classmethod
    def normalize_times(
        cls,
        values: list[str],
    ) -> list[str]:
        """校验、去重并按照一天中的时间排序。"""
        normalized: list[str] = []

        for value in values:
            cleaned = value.strip()

            if not SCHEDULE_TIME_PATTERN.fullmatch(cleaned):
                raise ValueError(
                    "执行时间必须使用 HH:MM 格式"
                )

            if cleaned not in normalized:
                normalized.append(cleaned)

        return sorted(normalized)


class DeliveryTarget(BaseModel):
    """一个投递目标。

    endpoint_env 和 token_env 保存环境变量名称，
    不直接保存密钥或令牌。
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    channel: DeliveryChannel = Field(
        description="投递渠道",
    )
    name: str = Field(
        min_length=1,
        max_length=100,
        description="投递目标名称",
    )
    enabled: bool = Field(
        default=True,
        description="是否启用",
    )
    endpoint_env: str | None = Field(
        default=None,
        description="接口地址所在环境变量名",
    )
    token_env: str | None = Field(
        default=None,
        description="访问令牌所在环境变量名",
    )
    options: dict[str, str] = Field(
        default_factory=dict,
        description="非敏感渠道参数",
    )


class TrackingTask(BaseModel):
    """用户可修改的完整政策追踪任务。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task_id: str = Field(
        default_factory=lambda: (
            f"policy-radar-{uuid4().hex[:8]}"
        ),
        min_length=3,
        max_length=64,
        description="任务唯一标识",
    )
    name: str = Field(
        min_length=1,
        max_length=120,
        description="任务显示名称",
    )
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="用户希望智能体回答的问题",
    )
    keywords: list[str] = Field(
        min_length=1,
        max_length=50,
        description="政策搜索关键词",
    )
    exclude_keywords: list[str] = Field(
        default_factory=list,
        max_length=50,
        description="搜索结果排除关键词",
    )
    source_config_path: str = Field(
        default=DEFAULT_SOURCE_CONFIG_PATH,
        min_length=1,
        description="政策源选择配置文件",
    )
    output_directory: str = Field(
        default=DEFAULT_OUTPUT_DIRECTORY,
        min_length=1,
        description="Markdown/JSON 简报根目录",
    )
    date_range: DateRangeConfig = Field(
        default_factory=DateRangeConfig,
        description="政策搜索时间范围",
    )
    schedule: TrackingSchedule = Field(
        default_factory=TrackingSchedule,
        description="每日调度时间",
    )
    max_results_per_source: int = Field(
        default=8,
        ge=1,
        le=50,
        description="每个来源最多搜索结果数",
    )
    max_candidates_per_run: int = Field(
        default=24,
        ge=1,
        le=200,
        description="每次最多下载并调用 LLM 的候选网页数",
    )
    max_policies_per_run: int = Field(
        default=12,
        ge=1,
        le=100,
        description="每次最多保留的新政策数",
    )
    only_new_policies: bool = Field(
        default=True,
        description="是否只投递尚未成功投递的政策",
    )
    send_when_no_updates: bool = Field(
        default=True,
        description="没有新政策时是否生成运行简报",
    )
    delivery_targets: list[DeliveryTarget] = Field(
        default_factory=lambda: [
            DeliveryTarget(
                channel=DeliveryChannel.LOCAL,
                name="本地报告",
            )
        ],
        min_length=1,
        description="投递目标列表",
    )

    @field_validator("task_id")
    @classmethod
    def task_id_must_be_safe(
        cls,
        value: str,
    ) -> str:
        """任务 ID 必须适合作为跨平台目录名。"""
        cleaned = value.casefold()

        if not TASK_ID_PATTERN.fullmatch(cleaned):
            raise ValueError(
                "task_id 只能包含小写字母、数字、"
                "下划线和连字符"
            )

        return cleaned

    @field_validator(
        "keywords",
        "exclude_keywords",
    )
    @classmethod
    def normalize_keywords(
        cls,
        values: list[str],
    ) -> list[str]:
        """清理空值并去重。"""
        normalized: list[str] = []

        for value in values:
            cleaned = value.strip()

            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)

        return normalized

    @model_validator(mode="after")
    def at_least_one_delivery_target(
        self,
    ) -> "TrackingTask":
        """至少需要启用一个投递目标。"""
        if not any(
            target.enabled
            for target in self.delivery_targets
        ):
            raise ValueError(
                "至少需要启用一个投递目标"
            )

        return self


class TrackingTaskState(BaseModel):
    """任务的持久化运行状态。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    task_id: str = Field(
        min_length=1,
        description="任务 ID",
    )
    last_started_at: datetime | None = Field(
        default=None,
        description="最近一次开始运行时间",
    )
    last_successful_at: datetime | None = Field(
        default=None,
        description="最近一次成功运行时间",
    )
    delivered_fingerprints: list[str] = Field(
        default_factory=list,
        description="已经成功投递的政策指纹",
    )
    failed_runs: int = Field(
        default=0,
        ge=0,
        description="连续或累计失败次数",
    )
    last_error: str | None = Field(
        default=None,
        description="最近一次运行错误",
    )

    @field_validator("delivered_fingerprints")
    @classmethod
    def fingerprints_are_unique(
        cls,
        values: list[str],
    ) -> list[str]:
        """政策指纹去重并保持原顺序。"""
        return list(dict.fromkeys(values))


def save_tracking_task(
    task: TrackingTask,
    output_path: str | Path,
) -> Path:
    """保存用户追踪任务配置。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        task.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    return path


def load_tracking_task(
    input_path: str | Path,
) -> TrackingTask:
    """读取并校验追踪任务配置。"""
    path = Path(input_path)

    if not path.is_file():
        raise TrackingTaskError(
            f"追踪任务文件不存在：{path}"
        )

    try:
        return TrackingTask.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except OSError as exc:
        raise TrackingTaskError(
            f"无法读取追踪任务：{path}；{exc}"
        ) from exc
    except ValidationError as exc:
        raise TrackingTaskError(
            f"追踪任务配置无效：{path}；{exc}"
        ) from exc


def save_tracking_state(
    state: TrackingTaskState,
    output_path: str | Path,
) -> Path:
    """保存任务运行状态。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        state.model_dump_json(
            indent=2,
            exclude_none=True,
        ),
        encoding="utf-8",
    )

    return path


def load_tracking_state(
    input_path: str | Path,
    *,
    task_id: str,
) -> TrackingTaskState:
    """读取状态；首次运行时创建空状态。"""
    path = Path(input_path)

    if not path.exists():
        return TrackingTaskState(
            task_id=task_id,
        )

    try:
        state = TrackingTaskState.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        ValidationError,
    ) as exc:
        raise TrackingTaskError(
            f"任务状态文件无效：{path}；{exc}"
        ) from exc

    if state.task_id != task_id:
        raise TrackingTaskError(
            "任务状态文件中的 task_id 与当前任务不一致"
        )

    return state
