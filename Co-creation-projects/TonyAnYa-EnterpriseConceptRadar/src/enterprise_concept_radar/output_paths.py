"""解析、校验并组织用户指定的本地报告目录。"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from enterprise_concept_radar.config import PROJECT_ROOT
from enterprise_concept_radar.tracking_tasks import TrackingTask

WINDOWS_ENV_PATTERN = re.compile(r"%([^%]+)%")
LATEST_FILENAMES = (
    "policy_brief.md",
    "policy_brief.json",
    "collection_run.json",
    "intelligence_brief.md",
    "intelligence_brief.json",
    "intelligence_run.json",
    "delivery_receipts.json",
)


class OutputPathError(RuntimeError):
    """输出目录无效、无法创建或不可写。"""


@dataclass(frozen=True, slots=True)
class TrackingOutputPaths:
    """一次追踪任务使用的全部输出路径。"""

    base_directory: Path
    task_directory: Path
    run_directory: Path
    latest_directory: Path
    local_started_at: datetime


def _expand_windows_environment_variables(
    value: str,
) -> str:
    """兼容展开 Windows 风格的 %NAME% 环境变量。"""

    def replace_match(
        match: re.Match[str],
    ) -> str:
        variable_name = match.group(1)

        return os.environ.get(
            variable_name,
            match.group(0),
        )

    return WINDOWS_ENV_PATTERN.sub(
        replace_match,
        value,
    )


def normalize_user_path(
    value: str,
) -> str:
    """清理用户输入、Finder 拖放路径和外层引号。"""
    cleaned = value.strip()

    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        cleaned = cleaned[1:-1]

    # Finder 将含空格路径拖入终端时可能显示反斜杠转义。
    cleaned = cleaned.replace(r"\ ", " ")

    if not cleaned:
        raise OutputPathError(
            "本地报告保存位置不能为空"
        )

    return cleaned


def resolve_output_directory(
    value: str,
    *,
    project_root: str | Path = PROJECT_ROOT,
    create: bool = True,
    check_writable: bool = True,
) -> Path:
    """解析跨平台输出路径并检查目录可写性。"""
    cleaned = normalize_user_path(value)
    expanded = _expand_windows_environment_variables(
        cleaned
    )
    expanded = os.path.expandvars(expanded)
    path = Path(expanded).expanduser()

    if not path.is_absolute():
        path = Path(project_root) / path

    path = path.resolve(strict=False)

    if path.exists() and not path.is_dir():
        raise OutputPathError(
            f"报告保存位置不是目录：{path}"
        )

    if create:
        try:
            path.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            raise OutputPathError(
                f"无法创建报告目录：{path}；{exc}"
            ) from exc

    if check_writable:
        if not path.is_dir():
            raise OutputPathError(
                f"报告目录不存在：{path}"
            )

        test_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=".enterprise-concept-radar-",
                suffix=".tmp",
                dir=path,
                delete=False,
            ) as test_file:
                test_file.write("write-check")
                test_path = Path(test_file.name)
        except OSError as exc:
            raise OutputPathError(
                f"报告目录不可写：{path}；{exc}"
            ) from exc
        finally:
            if test_path is not None:
                test_path.unlink(missing_ok=True)

    return path


def _choose_run_directory(
    desired_path: Path,
) -> Path:
    """避免同一秒重复手动运行时覆盖既有结果。"""
    if not desired_path.exists():
        return desired_path

    for index in range(1, 1000):
        candidate = desired_path.with_name(
            f"{desired_path.name}-{index:02d}"
        )

        if not candidate.exists():
            return candidate

    raise OutputPathError(
        "同一时间点的运行目录数量过多"
    )


def build_tracking_output_paths(
    *,
    task: TrackingTask,
    started_at: datetime,
    project_root: str | Path = PROJECT_ROOT,
) -> TrackingOutputPaths:
    """生成“任务/日期/时间”和 latest 目录结构。"""
    if started_at.tzinfo is None:
        raise OutputPathError(
            "started_at 必须包含时区信息"
        )

    base_directory = resolve_output_directory(
        task.output_directory,
        project_root=project_root,
    )
    local_started_at = started_at.astimezone(
        ZoneInfo(task.schedule.timezone)
    )
    task_directory = (
        base_directory / task.task_id
    )
    date_directory = (
        task_directory
        / local_started_at.strftime("%Y-%m-%d")
    )
    desired_run_directory = (
        date_directory
        / local_started_at.strftime("%H%M%S")
    )
    run_directory = _choose_run_directory(
        desired_run_directory
    )
    latest_directory = (
        task_directory / "latest"
    )

    try:
        run_directory.mkdir(
            parents=True,
            exist_ok=False,
        )
        latest_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
    except OSError as exc:
        raise OutputPathError(
            f"无法创建任务输出目录：{exc}"
        ) from exc

    return TrackingOutputPaths(
        base_directory=base_directory,
        task_directory=task_directory,
        run_directory=run_directory,
        latest_directory=latest_directory,
        local_started_at=local_started_at,
    )


def publish_latest_files(
    *,
    run_directory: str | Path,
    latest_directory: str | Path,
    filenames: tuple[str, ...] = LATEST_FILENAMES,
) -> list[Path]:
    """复制本次关键结果，使 latest 始终指向最近成功运行。"""
    source_directory = Path(run_directory)
    destination_directory = Path(
        latest_directory
    )
    destination_directory.mkdir(
        parents=True,
        exist_ok=True,
    )
    published: list[Path] = []

    for filename in filenames:
        source_path = (
            source_directory / filename
        )
        destination_path = (
            destination_directory / filename
        )

        if source_path.is_file():
            shutil.copy2(
                source_path,
                destination_path,
            )
            published.append(destination_path)
        else:
            destination_path.unlink(
                missing_ok=True
            )

    return published
