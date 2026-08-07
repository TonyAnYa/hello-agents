"""测试用户指定输出目录和 latest 发布。"""

from datetime import datetime, timezone

import pytest

from enterprise_concept_radar.output_paths import (
    OutputPathError,
    build_tracking_output_paths,
    publish_latest_files,
    resolve_output_directory,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
)


def build_task(
    output_directory: str,
) -> TrackingTask:
    """创建输出目录测试任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="今天有哪些政策？",
        keywords=["新能源"],
        output_directory=output_directory,
    )


def test_relative_output_path_uses_project_root(
    tmp_path,
) -> None:
    """相对路径应以项目根目录为起点。"""
    resolved = resolve_output_directory(
        "reports",
        project_root=tmp_path,
    )

    assert resolved == (
        tmp_path / "reports"
    ).resolve()
    assert resolved.is_dir()


def test_output_path_rejects_existing_file(
    tmp_path,
) -> None:
    """普通文件不能作为报告目录。"""
    file_path = tmp_path / "not-a-directory"
    file_path.write_text(
        "content",
        encoding="utf-8",
    )

    with pytest.raises(
        OutputPathError,
        match="不是目录",
    ):
        resolve_output_directory(
            str(file_path)
        )


def test_build_output_paths_uses_task_timezone(
    tmp_path,
) -> None:
    """UTC 时间应转换成任务配置的北京时间目录。"""
    task = build_task(str(tmp_path))
    paths = build_tracking_output_paths(
        task=task,
        started_at=datetime(
            2026,
            8,
            7,
            0,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert paths.run_directory == (
        tmp_path
        / "energy-policy-radar"
        / "2026-08-07"
        / "083000"
    )
    assert paths.latest_directory.is_dir()


def test_publish_latest_files_copies_reports(
    tmp_path,
) -> None:
    """latest 应复制最近一次成功运行的关键文件。"""
    run_directory = tmp_path / "run"
    latest_directory = tmp_path / "latest"
    run_directory.mkdir()
    (run_directory / "policy_brief.md").write_text(
        "# 最新简报",
        encoding="utf-8",
    )
    (run_directory / "policy_brief.json").write_text(
        '{"ok": true}',
        encoding="utf-8",
    )

    published = publish_latest_files(
        run_directory=run_directory,
        latest_directory=latest_directory,
    )

    assert len(published) == 2
    assert (
        latest_directory / "policy_brief.md"
    ).read_text(encoding="utf-8") == "# 最新简报"
