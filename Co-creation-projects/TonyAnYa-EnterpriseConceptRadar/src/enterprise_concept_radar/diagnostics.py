"""无需联网的安装、代码与运行配置自检。"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values

from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    CONFIG_DIR,
    PROJECT_ROOT,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.output_paths import (
    resolve_output_directory,
)
from enterprise_concept_radar.policy_sources import (
    load_policy_source_selection,
)
from enterprise_concept_radar.scoring import (
    load_concept_baseline,
)
from enterprise_concept_radar.tools import (
    load_concept_rules,
)
from enterprise_concept_radar.tracking_tasks import (
    load_tracking_task,
)

DiagnosticStatus = Literal[
    "PASS",
    "WARN",
    "FAIL",
]

REQUIRED_ENVIRONMENT_NAMES = (
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "LLM_BASE_URL",
    "SERPAPI_API_KEY",
)
REQUIRED_IMPORTS = {
    "pydantic": "pydantic",
    "requests": "requests",
    "python-dotenv": "dotenv",
    "PyYAML": "yaml",
    "beautifulsoup4": "bs4",
    "hello-agents": "hello_agents",
}
REQUIRED_PROMPTS = (
    "answer_composer.md",
    "business_impact.md",
    "concept_analysis.md",
    "concept_discovery.md",
    "policy_document_extractor.md",
    "policy_source_resolver.md",
)
REQUIRED_LAUNCHERS = (
    "setup_macos.command",
    "start_macos.command",
    "radar_macos.command",
    "setup_windows.cmd",
    "start_windows.cmd",
    "radar_windows.cmd",
)


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    """一项离线诊断结果。"""

    status: DiagnosticStatus
    name: str
    message: str


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """全部离线诊断结果。"""

    checks: tuple[DiagnosticCheck, ...]

    @property
    def failure_count(self) -> int:
        """失败检查数量。"""
        return sum(
            check.status == "FAIL"
            for check in self.checks
        )

    @property
    def warning_count(self) -> int:
        """警告检查数量。"""
        return sum(
            check.status == "WARN"
            for check in self.checks
        )

    @property
    def passed(self) -> bool:
        """没有失败项时诊断通过。"""
        return self.failure_count == 0


def _check(
    status: DiagnosticStatus,
    name: str,
    message: str,
) -> DiagnosticCheck:
    """创建诊断结果。"""
    return DiagnosticCheck(
        status=status,
        name=name,
        message=message,
    )


def check_python_version() -> DiagnosticCheck:
    """检查支持的 Python 版本。"""
    version = sys.version_info[:3]
    supported = (
        (3, 10) <= version[:2] < (3, 13)
    )
    status: DiagnosticStatus = (
        "PASS" if supported else "FAIL"
    )

    return _check(
        status,
        "Python",
        ".".join(str(item) for item in version),
    )


def check_dependencies() -> list[DiagnosticCheck]:
    """只检查包是否可导入，不访问网络。"""
    checks = []

    for display_name, import_name in (
        REQUIRED_IMPORTS.items()
    ):
        found = (
            importlib.util.find_spec(
                import_name
            )
            is not None
        )
        checks.append(
            _check(
                "PASS" if found else "FAIL",
                f"依赖 {display_name}",
                (
                    "已安装"
                    if found
                    else "未安装，请重新运行安装脚本"
                ),
            )
        )

    return checks


def check_project_files(
    project_root: Path,
) -> list[DiagnosticCheck]:
    """检查提示词、规则、基线和启动入口。"""
    checks: list[DiagnosticCheck] = []

    for filename in REQUIRED_PROMPTS:
        path = (
            project_root
            / "config"
            / "prompts"
            / filename
        )
        valid = (
            path.is_file()
            and bool(
                path.read_text(
                    encoding="utf-8"
                ).strip()
            )
        )
        checks.append(
            _check(
                "PASS" if valid else "FAIL",
                f"提示词 {filename}",
                (
                    str(path)
                    if valid
                    else "文件不存在或为空"
                ),
            )
        )

    for filename in REQUIRED_LAUNCHERS:
        path = project_root / filename
        checks.append(
            _check(
                (
                    "PASS"
                    if path.is_file()
                    else "FAIL"
                ),
                f"启动入口 {filename}",
                (
                    str(path)
                    if path.is_file()
                    else "文件不存在"
                ),
            )
        )

    try:
        load_concept_rules(
            CONFIG_DIR / "concept_rules.yaml"
        )
        checks.append(
            _check(
                "PASS",
                "概念发现规则",
                "格式有效",
            )
        )
    except Exception as exc:
        checks.append(
            _check(
                "FAIL",
                "概念发现规则",
                f"{type(exc).__name__}: {exc}",
            )
        )

    try:
        load_concept_baseline(
            BASELINE_DATA_DIR
            / "known_terms.json"
        )
        checks.append(
            _check(
                "PASS",
                "历史术语基线",
                "格式有效",
            )
        )
    except Exception as exc:
        checks.append(
            _check(
                "FAIL",
                "历史术语基线",
                f"{type(exc).__name__}: {exc}",
            )
        )

    return checks


def check_environment(
    *,
    project_root: Path,
    require_runtime: bool,
) -> DiagnosticCheck:
    """只报告缺失变量名，不输出任何密钥值。"""
    env_path = project_root / ".env"

    if not env_path.is_file():
        return _check(
            (
                "FAIL"
                if require_runtime
                else "WARN"
            ),
            "环境变量",
            (
                "尚未创建 .env"
                if not require_runtime
                else "缺少 .env，无法正式运行"
            ),
        )

    values = dotenv_values(env_path)
    missing = [
        name
        for name in REQUIRED_ENVIRONMENT_NAMES
        if not str(
            values.get(name) or ""
        ).strip()
    ]

    if missing:
        return _check(
            (
                "FAIL"
                if require_runtime
                else "WARN"
            ),
            "环境变量",
            "缺少：" + "、".join(missing),
        )

    return _check(
        "PASS",
        "环境变量",
        "必要变量均已填写；未显示任何秘密值",
    )


def check_runtime_tasks(
    *,
    project_root: Path,
    require_runtime: bool,
) -> list[DiagnosticCheck]:
    """检查任务、来源和用户输出目录。"""
    tasks_directory = (
        RUNTIME_DATA_DIR
        / "tracking"
        / "tasks"
    )
    task_paths = sorted(
        tasks_directory.glob("*.json")
    )

    if not task_paths:
        return [
            _check(
                (
                    "FAIL"
                    if require_runtime
                    else "WARN"
                ),
                "追踪任务",
                "尚未配置追踪任务",
            )
        ]

    checks: list[DiagnosticCheck] = []

    for task_path in task_paths:
        try:
            task = load_tracking_task(
                task_path
            )
            output_directory = (
                resolve_output_directory(
                    task.output_directory,
                    project_root=project_root,
                )
            )
            checks.append(
                _check(
                    "PASS",
                    f"追踪任务 {task.task_id}",
                    (
                        "配置有效；输出目录："
                        f"{output_directory}"
                    ),
                )
            )
        except Exception as exc:
            checks.append(
                _check(
                    "FAIL",
                    f"追踪任务 {task_path.name}",
                    f"{type(exc).__name__}: {exc}",
                )
            )
            continue

        source_path = Path(
            task.source_config_path
        ).expanduser()

        if not source_path.is_absolute():
            source_path = (
                project_root / source_path
            )

        try:
            selection = (
                load_policy_source_selection(
                    source_path
                )
            )
            source_names = [
                source.name
                or source.source_id
                for source
                in selection.selected_sources()
            ]
            checks.append(
                _check(
                    "PASS",
                    f"政策来源 {task.task_id}",
                    "、".join(source_names),
                )
            )
        except Exception as exc:
            checks.append(
                _check(
                    "FAIL",
                    f"政策来源 {task.task_id}",
                    f"{type(exc).__name__}: {exc}",
                )
            )

    return checks


def run_offline_diagnostics(
    *,
    project_root: str | Path = PROJECT_ROOT,
    require_runtime: bool = False,
) -> DiagnosticReport:
    """执行全部离线自检。"""
    root = Path(project_root).resolve()
    checks: list[DiagnosticCheck] = [
        check_python_version(),
        *check_dependencies(),
        *check_project_files(root),
        check_environment(
            project_root=root,
            require_runtime=require_runtime,
        ),
        *check_runtime_tasks(
            project_root=root,
            require_runtime=require_runtime,
        ),
    ]

    return DiagnosticReport(
        checks=tuple(checks)
    )
