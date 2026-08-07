"""测试发行包不会泄露密钥和本地运行数据。"""

import json
import zipfile

import pytest

from enterprise_concept_radar.release import (
    ReleaseBuildError,
    assert_release_files_safe,
    build_release_archive,
    is_release_file,
    iter_release_files,
    load_local_sensitive_values,
)

DEEPSEEK_TEST_SECRET = (
    "test-deepseek-secret-123456789"
)
SERPAPI_TEST_SECRET = (
    "test-serpapi-secret-987654321"
)


def build_fake_project(tmp_path):
    """创建包含安全文件和敏感文件的最小项目。"""
    files = {
        "pyproject.toml": (
            "[project]\nname='test'\n"
        ),
        ".env.example": (
            "LLM_API_KEY=\n"
            "SERPAPI_API_KEY=\n"
        ),
        ".env": (
            f"LLM_API_KEY={DEEPSEEK_TEST_SECRET}\n"
            f"SERPAPI_API_KEY={SERPAPI_TEST_SECRET}\n"
        ),
        "README.md": "# Test\n",
        "src/package/__init__.py": "",
        "scripts/run.py": "print('ok')\n",
        "tests/test_ok.py": (
            "def test_ok(): pass\n"
        ),
        "data/sample/example.json": "{}\n",
        "data/runtime/state.json": (
            '{"secret": true}\n'
        ),
        "outputs/reports/report.md": (
            "private\n"
        ),
        "outputs/reports/.gitkeep": "",
        ".venv/bin/python": "binary\n",
        "dist/old.zip": "archive\n",
    }

    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            content,
            encoding="utf-8",
        )

    return tmp_path


def test_release_file_policy() -> None:
    """敏感路径必须被拒绝，公开模板必须保留。"""
    assert is_release_file(".env.example")
    assert not is_release_file(".env")
    assert not is_release_file(
        "data/runtime/task.json"
    )
    assert not is_release_file(
        "outputs/reports/report.md"
    )
    assert is_release_file(
        "outputs/reports/.gitkeep"
    )
    assert is_release_file(
        "src/package/module.py"
    )


def test_iter_release_files_excludes_local_data(
    tmp_path,
) -> None:
    """文件列表不得包含秘密和运行结果。"""
    project = build_fake_project(
        tmp_path
    )
    relative_paths = {
        path.relative_to(project).as_posix()
        for path in iter_release_files(project)
    }

    assert ".env.example" in relative_paths
    assert ".env" not in relative_paths
    assert (
        "data/runtime/state.json"
        not in relative_paths
    )
    assert (
        "outputs/reports/report.md"
        not in relative_paths
    )
    assert (
        "outputs/reports/.gitkeep"
        in relative_paths
    )


def test_local_secret_values_are_loaded_only_for_scan(
    tmp_path,
) -> None:
    """只收集秘密变量，普通公开配置不纳入扫描。"""
    project = build_fake_project(
        tmp_path
    )
    values = load_local_sensitive_values(
        project
    )

    assert values == {
        "LLM_API_KEY": (
            DEEPSEEK_TEST_SECRET
        ),
        "SERPAPI_API_KEY": (
            SERPAPI_TEST_SECRET
        ),
    }


def test_release_refuses_secret_copied_into_readme(
    tmp_path,
) -> None:
    """即使 .env 被排除，误粘贴到其他文件的 Key 也必须拦截。"""
    project = build_fake_project(
        tmp_path
    )
    readme = project / "README.md"
    readme.write_text(
        "# Test\n"
        f"accidental={DEEPSEEK_TEST_SECRET}\n",
        encoding="utf-8",
    )
    selected = iter_release_files(
        project
    )

    with pytest.raises(
        ReleaseBuildError,
        match="LLM_API_KEY",
    ):
        assert_release_files_safe(
            project_root=project,
            files=selected,
        )


def test_build_release_archive_has_manifest(
    tmp_path,
) -> None:
    """发行 ZIP 应有单一顶层目录和安全清单。"""
    project = build_fake_project(
        tmp_path / "project"
    )
    result = build_release_archive(
        project_root=project,
        destination_directory=(
            tmp_path / "release"
        ),
        version="9.9.9",
        source_commit="abc1234",
    )

    with zipfile.ZipFile(
        result.archive_path
    ) as archive:
        names = archive.namelist()
        prefix = (
            "EnterpriseConceptRadar-9.9.9/"
        )
        assert all(
            name.startswith(prefix)
            for name in names
        )
        assert (
            prefix + ".env"
            not in names
        )
        archive_bytes = b"".join(
            archive.read(name)
            for name in names
            if not name.endswith("/")
        )
        manifest = json.loads(
            archive.read(
                prefix
                + "RELEASE_MANIFEST.json"
            )
        )

    assert DEEPSEEK_TEST_SECRET.encode() not in (
        archive_bytes
    )
    assert SERPAPI_TEST_SECRET.encode() not in (
        archive_bytes
    )
    assert manifest["source_commit"] == (
        "abc1234"
    )
    assert manifest[
        "security_checks"
    ][
        "local_secret_value_scan"
    ] is True
