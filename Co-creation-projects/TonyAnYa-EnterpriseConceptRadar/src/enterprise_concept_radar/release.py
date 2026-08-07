"""构建不包含密钥和运行数据的跨平台发行压缩包。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping

from dotenv import dotenv_values

PROJECT_VERSION = "0.1.0"
DEFAULT_RELEASE_PREFIX = "EnterpriseConceptRadar"

ROOT_FILE_NAMES = {
    ".env.example",
    ".gitignore",
    "README.md",
    "main.ipynb",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "setup_macos.command",
    "setup_windows.cmd",
    "start_macos.command",
    "start_windows.cmd",
    "radar_macos.command",
    "radar_windows.cmd",
}
ALLOWED_TOP_LEVEL_DIRECTORIES = {
    "config",
    "data",
    "docs",
    "outputs",
    "scripts",
    "src",
    "tests",
}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".github",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "env",
    "venv",
}
EXCLUDED_FILE_SUFFIXES = {
    ".7z",
    ".db",
    ".dmg",
    ".exe",
    ".log",
    ".parquet",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tgz",
    ".zip",
}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    ".env",
    ".env.local",
}
SENSITIVE_PATH_PREFIXES = {
    ("data", "runtime"),
}
GENERATED_OUTPUT_DIRECTORIES = {
    ("outputs", "concept_cards"),
    ("outputs", "reports"),
    ("outputs", "screenshots"),
}
SENSITIVE_NAME_MARKERS = (
    "API_KEY",
    "TOKEN",
    "PASSWORD",
    "SECRET",
)
MINIMUM_SCANNED_SECRET_LENGTH = 8
MAX_SCANNED_TEXT_FILE_BYTES = (
    5 * 1024 * 1024
)


class ReleaseBuildError(RuntimeError):
    """发行包内容无效或压缩包创建失败。"""


@dataclass(frozen=True, slots=True)
class ReleaseBuildResult:
    """一次发行包构建结果。"""

    archive_path: Path
    archive_sha256: str
    file_count: int
    release_root_name: str
    source_commit: str | None


def file_sha256(path: str | Path) -> str:
    """计算文件 SHA-256。"""
    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _path_starts_with(
    relative_path: PurePosixPath,
    prefix: tuple[str, ...],
) -> bool:
    """判断路径是否具有指定目录前缀。"""
    parts = relative_path.parts

    return tuple(parts[: len(prefix)]) == prefix


def is_release_file(
    relative_path: str | PurePosixPath,
) -> bool:
    """判断一个项目相对路径是否应进入发行包。"""
    path = PurePosixPath(relative_path)
    parts = path.parts

    if not parts:
        return False

    if any(
        part in EXCLUDED_DIRECTORY_NAMES
        for part in parts[:-1]
    ):
        return False

    if path.name in EXCLUDED_FILE_NAMES:
        return False

    if (
        path.name.startswith(".env.")
        and path.name != ".env.example"
    ):
        return False

    if path.name.startswith(
        ("README_APPLY_", "MANIFEST_")
    ):
        return False

    if path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
        return False

    if any(
        _path_starts_with(path, prefix)
        for prefix in SENSITIVE_PATH_PREFIXES
    ):
        return False

    for prefix in GENERATED_OUTPUT_DIRECTORIES:
        if _path_starts_with(path, prefix):
            return path.name == ".gitkeep"

    if len(parts) == 1:
        return path.name in ROOT_FILE_NAMES

    return parts[0] in ALLOWED_TOP_LEVEL_DIRECTORIES


def iter_release_files(
    project_root: str | Path,
) -> list[Path]:
    """返回稳定排序的发行文件列表。"""
    root = Path(project_root).resolve()

    if not (root / "pyproject.toml").is_file():
        raise ReleaseBuildError(
            f"不是有效的项目根目录：{root}"
        )

    selected: list[Path] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = PurePosixPath(
            path.relative_to(root).as_posix()
        )

        if is_release_file(relative):
            selected.append(path)

    selected.sort(
        key=lambda item: (
            item.relative_to(root).as_posix()
        )
    )

    if not selected:
        raise ReleaseBuildError(
            "没有找到可打包文件"
        )

    return selected


def load_local_sensitive_values(
    project_root: str | Path,
) -> dict[str, str]:
    """读取本机秘密用于泄露扫描，不返回到清单或日志。"""
    env_path = (
        Path(project_root).resolve()
        / ".env"
    )

    if not env_path.is_file():
        return {}

    try:
        values = dotenv_values(env_path)
    except OSError as exc:
        raise ReleaseBuildError(
            f"无法读取本机 .env 进行安全扫描：{exc}"
        ) from exc

    sensitive: dict[str, str] = {}

    for name, raw_value in values.items():
        if not name or raw_value is None:
            continue

        normalized_name = str(name).upper()

        if not any(
            marker in normalized_name
            for marker in SENSITIVE_NAME_MARKERS
        ):
            continue

        value = str(raw_value).strip()

        if (
            len(value)
            >= MINIMUM_SCANNED_SECRET_LENGTH
        ):
            sensitive[str(name)] = value

    return sensitive


def _read_text_for_secret_scan(
    path: Path,
) -> str | None:
    """读取小型 UTF-8 文本；二进制或大文件跳过。"""
    try:
        if (
            path.stat().st_size
            > MAX_SCANNED_TEXT_FILE_BYTES
        ):
            return None

        return path.read_text(
            encoding="utf-8"
        )
    except (
        UnicodeDecodeError,
        OSError,
    ):
        return None


def find_secret_leaks(
    *,
    project_root: str | Path,
    files: Iterable[Path],
    sensitive_values: Mapping[
        str,
        str,
    ] | None = None,
) -> dict[str, list[str]]:
    """查找本机秘密被误复制到待发行文本文件的情况。"""
    root = Path(project_root).resolve()
    secrets = dict(
        sensitive_values
        if sensitive_values is not None
        else load_local_sensitive_values(
            root
        )
    )
    leaks: dict[str, list[str]] = {}

    if not secrets:
        return leaks

    for path in files:
        content = _read_text_for_secret_scan(
            path
        )

        if content is None:
            continue

        matched_names = [
            name
            for name, value in secrets.items()
            if value and value in content
        ]

        if matched_names:
            relative_path = (
                path.relative_to(root)
                .as_posix()
            )
            leaks[relative_path] = sorted(
                matched_names
            )

    return leaks


def assert_release_files_safe(
    *,
    project_root: str | Path,
    files: Iterable[Path],
    sensitive_values: Mapping[
        str,
        str,
    ] | None = None,
) -> None:
    """发现本机密钥副本时拒绝创建发行包。"""
    leaks = find_secret_leaks(
        project_root=project_root,
        files=files,
        sensitive_values=sensitive_values,
    )

    if not leaks:
        return

    details = "；".join(
        f"{path}：{','.join(names)}"
        for path, names in sorted(
            leaks.items()
        )
    )

    raise ReleaseBuildError(
        "安全检查失败：发现本机秘密值被复制到"
        f"待打包文件。请先清理：{details}。"
        "错误信息不会显示秘密值。"
    )


def detect_source_commit(
    project_root: str | Path,
) -> str | None:
    """读取当前 Git 提交；非 Git 目录时返回 None。"""
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            cwd=Path(project_root),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ):
        return None

    value = result.stdout.strip()

    return value or None


def build_release_manifest(
    *,
    project_root: Path,
    files: Iterable[Path],
    version: str,
    source_commit: str | None,
) -> dict[str, object]:
    """生成不含秘密值的发行文件清单。"""
    entries = []

    for path in files:
        relative_path = (
            path.relative_to(project_root)
            .as_posix()
        )
        entries.append(
            {
                "path": relative_path,
                "size_bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )

    return {
        "product": "EnterpriseConceptRadar",
        "version": version,
        "source_commit": source_commit,
        "built_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "file_count": len(entries),
        "files": entries,
        "security_checks": {
            "env_file_excluded": True,
            "runtime_data_excluded": True,
            "local_secret_value_scan": True,
        },
        "excluded_local_data": [
            ".env",
            ".venv/",
            "data/runtime/",
            "outputs 中的运行结果",
            "build/",
            "dist/",
            "Git 元数据",
        ],
    }


def _zip_info(
    *,
    source_path: Path,
    archive_name: str,
) -> zipfile.ZipInfo:
    """创建保留 Unix 可执行权限的 ZIP 条目。"""
    info = zipfile.ZipInfo.from_file(
        source_path,
        arcname=archive_name,
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    mode = source_path.stat().st_mode
    info.external_attr = (
        mode & 0xFFFF
    ) << 16

    return info


def verify_archive_safety(
    *,
    archive_path: str | Path,
    release_root_name: str,
    sensitive_values: Mapping[
        str,
        str,
    ],
) -> None:
    """构建后再次检查 ZIP 名称和文件内容。"""
    prefix = f"{release_root_name}/"

    try:
        with zipfile.ZipFile(
            archive_path
        ) as archive:
            for member in archive.infolist():
                name = member.filename
                relative_name = name.removeprefix(
                    prefix
                )
                relative_path = PurePosixPath(
                    relative_name
                )

                if not name.startswith(prefix):
                    raise ReleaseBuildError(
                        "发行 ZIP 存在顶层目录之外的文件"
                    )

                if relative_path.name == ".env":
                    raise ReleaseBuildError(
                        "发行 ZIP 错误包含 .env"
                    )

                if _path_starts_with(
                    relative_path,
                    ("data", "runtime"),
                ):
                    raise ReleaseBuildError(
                        "发行 ZIP 错误包含 data/runtime"
                    )

                if (
                    not sensitive_values
                    or member.is_dir()
                    or member.file_size
                    > MAX_SCANNED_TEXT_FILE_BYTES
                ):
                    continue

                raw_content = archive.read(
                    member
                )

                for variable_name, value in (
                    sensitive_values.items()
                ):
                    if (
                        value.encode("utf-8")
                        in raw_content
                    ):
                        raise ReleaseBuildError(
                            "发行 ZIP 安全复检失败："
                            f"{relative_name} 包含 "
                            f"{variable_name} 的本机值。"
                            "错误信息不会显示秘密值。"
                        )
    except zipfile.BadZipFile as exc:
        raise ReleaseBuildError(
            f"发行 ZIP 无效：{exc}"
        ) from exc


def build_release_archive(
    *,
    project_root: str | Path,
    destination_directory: str | Path,
    version: str = PROJECT_VERSION,
    source_commit: str | None = None,
) -> ReleaseBuildResult:
    """创建经两次秘密扫描的干净发行 ZIP。"""
    root = Path(project_root).resolve()
    destination = Path(
        destination_directory
    ).resolve()
    destination.mkdir(
        parents=True,
        exist_ok=True,
    )
    release_root_name = (
        f"{DEFAULT_RELEASE_PREFIX}-{version}"
    )
    archive_path = (
        destination
        / f"{release_root_name}.zip"
    )

    files = iter_release_files(root)
    sensitive_values = (
        load_local_sensitive_values(
            root
        )
    )
    assert_release_files_safe(
        project_root=root,
        files=files,
        sensitive_values=sensitive_values,
    )
    active_commit = (
        source_commit
        if source_commit is not None
        else detect_source_commit(root)
    )
    manifest = build_release_manifest(
        project_root=root,
        files=files,
        version=version,
        source_commit=active_commit,
    )

    try:
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source_path in files:
                relative_path = (
                    source_path.relative_to(root)
                    .as_posix()
                )
                archive_name = (
                    f"{release_root_name}/"
                    f"{relative_path}"
                )
                info = _zip_info(
                    source_path=source_path,
                    archive_name=archive_name,
                )

                with source_path.open("rb") as file:
                    archive.writestr(
                        info,
                        file.read(),
                    )

            manifest_name = (
                f"{release_root_name}/"
                "RELEASE_MANIFEST.json"
            )
            archive.writestr(
                manifest_name,
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
            )
    except OSError as exc:
        archive_path.unlink(
            missing_ok=True
        )
        raise ReleaseBuildError(
            f"无法创建发行压缩包：{exc}"
        ) from exc

    try:
        verify_archive_safety(
            archive_path=archive_path,
            release_root_name=(
                release_root_name
            ),
            sensitive_values=(
                sensitive_values
            ),
        )
    except Exception:
        archive_path.unlink(
            missing_ok=True
        )
        raise

    return ReleaseBuildResult(
        archive_path=archive_path,
        archive_sha256=file_sha256(
            archive_path
        ),
        file_count=len(files) + 1,
        release_root_name=(
            release_root_name
        ),
        source_commit=active_commit,
    )
