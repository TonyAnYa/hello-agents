"""启动调度器前验证密钥、来源、任务和输出目录。"""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values

from enterprise_concept_radar.config import (
    PROJECT_ROOT,
    RUNTIME_DATA_DIR,
)
from enterprise_concept_radar.output_paths import (
    resolve_output_directory,
)
from enterprise_concept_radar.policy_sources import (
    load_policy_source_selection,
)
from enterprise_concept_radar.tracking_tasks import (
    load_tracking_task,
)

REQUIRED_ENVIRONMENT_NAMES = (
    "LLM_API_KEY",
    "LLM_MODEL_ID",
    "LLM_BASE_URL",
    "SERPAPI_API_KEY",
)


def resolve_project_path(
    value: str | Path,
) -> Path:
    """解析项目配置中的相对路径。"""
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def validate_environment_file(
    path: str | Path,
) -> list[str]:
    """返回缺失或为空的必要环境变量名。"""
    values = dotenv_values(path)

    return [
        name
        for name in REQUIRED_ENVIRONMENT_NAMES
        if not str(values.get(name) or "").strip()
    ]


def main() -> None:
    """执行不联网的运行前配置检查。"""
    errors: list[str] = []
    env_path = PROJECT_ROOT / ".env"

    if not env_path.is_file():
        errors.append(
            f"缺少环境变量文件：{env_path}"
        )
    else:
        missing_names = (
            validate_environment_file(
                env_path
            )
        )

        if missing_names:
            errors.append(
                "以下环境变量尚未填写："
                + "、".join(missing_names)
            )

    tasks_directory = (
        RUNTIME_DATA_DIR
        / "tracking"
        / "tasks"
    )
    task_paths = sorted(
        tasks_directory.glob("*.json")
    )

    if not task_paths:
        errors.append(
            "尚未创建追踪任务，请运行 "
            "python scripts/configure_tracking_task.py"
        )

    checked_source_paths: set[Path] = set()

    for task_path in task_paths:
        try:
            task = load_tracking_task(
                task_path
            )
            output_directory = (
                resolve_output_directory(
                    task.output_directory,
                    project_root=PROJECT_ROOT,
                )
            )
            print(
                f"[任务正常] {task.task_id}；"
                f"输出目录：{output_directory}"
            )

            source_path = (
                resolve_project_path(
                    task.source_config_path
                )
            )

            if (
                source_path
                not in checked_source_paths
            ):
                selection = (
                    load_policy_source_selection(
                        source_path
                    )
                )
                checked_source_paths.add(
                    source_path
                )
                print(
                    "[来源正常] 已启用："
                    + "、".join(
                        source.name
                        or source.source_id
                        for source in (
                            selection
                            .selected_sources()
                        )
                    )
                )
        except Exception as exc:
            errors.append(
                f"{task_path.name}："
                f"{type(exc).__name__}: {exc}"
            )

    if errors:
        print()
        print("运行配置检查失败：")

        for error in errors:
            print(f"- {error}")

        raise SystemExit(1)

    print()
    print("运行配置检查通过。")


if __name__ == "__main__":
    main()
