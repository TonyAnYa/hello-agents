"""测试项目配置和跨平台路径。"""

from pathlib import Path

from enterprise_concept_radar.config import (
    CONCEPT_CARD_DIR,
    DATA_DIR,
    PROJECT_ROOT,
    REPORT_DIR,
    RUNTIME_DATA_DIR,
    ensure_runtime_directories,
)


def test_project_root_is_valid() -> None:
    """项目根目录应包含 pyproject.toml。"""
    assert isinstance(PROJECT_ROOT, Path)
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_project_directories_use_pathlib() -> None:
    """所有主要目录都应使用 pathlib.Path 表示。"""
    paths = [
        PROJECT_ROOT,
        DATA_DIR,
        RUNTIME_DATA_DIR,
        REPORT_DIR,
        CONCEPT_CARD_DIR,
    ]

    assert all(isinstance(path, Path) for path in paths)


def test_runtime_directories_can_be_created() -> None:
    """运行目录应能在不同操作系统中正常创建。"""
    ensure_runtime_directories()

    assert RUNTIME_DATA_DIR.is_dir()
    assert REPORT_DIR.is_dir()
    assert CONCEPT_CARD_DIR.is_dir()


def test_paths_are_inside_project() -> None:
    """运行目录不应意外写到项目外部。"""
    project_root = PROJECT_ROOT.resolve()

    managed_paths = [
        DATA_DIR,
        RUNTIME_DATA_DIR,
        REPORT_DIR,
        CONCEPT_CARD_DIR,
    ]

    for path in managed_paths:
        assert path.resolve().is_relative_to(project_root)