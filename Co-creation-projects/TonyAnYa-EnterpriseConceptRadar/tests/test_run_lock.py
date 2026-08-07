"""测试跨平台任务互斥锁。"""

import os
import time
from datetime import timedelta

import pytest

from enterprise_concept_radar.run_lock import (
    TaskAlreadyRunningError,
    task_run_lock,
)


def test_lock_is_created_and_released(
    tmp_path,
) -> None:
    """正常上下文应创建并最终删除锁文件。"""
    lock_path = (
        tmp_path / "energy-policy-radar.lock"
    )

    with task_run_lock(
        "energy-policy-radar",
        lock_directory=tmp_path,
    ):
        assert lock_path.is_file()

    assert not lock_path.exists()


def test_second_process_style_lock_is_rejected(
    tmp_path,
) -> None:
    """已有活动锁时第二次取得必须失败。"""
    first = task_run_lock(
        "energy-policy-radar",
        lock_directory=tmp_path,
    )
    first.acquire()

    try:
        with pytest.raises(
            TaskAlreadyRunningError,
            match="已经在运行",
        ):
            task_run_lock(
                "energy-policy-radar",
                lock_directory=tmp_path,
            ).acquire()
    finally:
        first.release()


def test_stale_lock_is_replaced(
    tmp_path,
) -> None:
    """超过过期时间的异常遗留锁应被自动清理。"""
    lock_path = (
        tmp_path / "energy-policy-radar.lock"
    )
    lock_path.write_text(
        '{"token": "old", "pid": 1}',
        encoding="utf-8",
    )
    old_time = time.time() - 7200
    os.utime(
        lock_path,
        (old_time, old_time),
    )

    with task_run_lock(
        "energy-policy-radar",
        lock_directory=tmp_path,
        stale_after=timedelta(hours=1),
    ):
        assert '"old"' not in (
            lock_path.read_text(
                encoding="utf-8"
            )
        )
