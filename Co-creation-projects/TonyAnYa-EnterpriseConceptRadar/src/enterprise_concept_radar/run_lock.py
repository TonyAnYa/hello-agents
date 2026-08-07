"""跨平台任务互斥锁，防止同一任务重复并发运行。"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from enterprise_concept_radar.config import (
    RUNTIME_DATA_DIR,
)


class TaskRunLockError(RuntimeError):
    """任务锁创建、读取或释放失败。"""


class TaskAlreadyRunningError(
    TaskRunLockError
):
    """同一追踪任务已经由另一个进程运行。"""


class TaskRunLock:
    """使用原子文件创建实现的跨平台互斥锁。"""

    def __init__(
        self,
        *,
        task_id: str,
        lock_directory: str | Path | None = None,
        stale_after: timedelta = timedelta(
            hours=24
        ),
    ) -> None:
        self.task_id = task_id
        self.lock_directory = (
            Path(lock_directory)
            if lock_directory is not None
            else (
                RUNTIME_DATA_DIR
                / "tracking"
                / "locks"
            )
        )
        self.lock_path = (
            self.lock_directory
            / f"{task_id}.lock"
        )
        self.stale_after = stale_after
        self.token = uuid4().hex
        self.acquired = False

    def _lock_is_stale(self) -> bool:
        """根据文件更新时间判断异常遗留锁。"""
        try:
            modified_at = (
                self.lock_path.stat().st_mtime
            )
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise TaskRunLockError(
                f"无法读取任务锁状态：{exc}"
            ) from exc

        age_seconds = max(
            0.0,
            time.time() - modified_at,
        )

        return age_seconds > (
            self.stale_after.total_seconds()
        )

    def _existing_lock_summary(self) -> str:
        """读取现有锁的可读信息。"""
        try:
            raw_text = self.lock_path.read_text(
                encoding="utf-8"
            )
            payload = json.loads(raw_text)
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return str(self.lock_path)

        pid = payload.get("pid")
        started_at = payload.get(
            "started_at"
        )

        return (
            f"{self.lock_path}"
            f"（PID={pid}，开始时间={started_at}）"
        )

    def acquire(self) -> None:
        """原子创建任务锁；过期锁会被清理一次。"""
        self.lock_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        for attempt in range(2):
            try:
                descriptor = os.open(
                    self.lock_path,
                    (
                        os.O_CREAT
                        | os.O_EXCL
                        | os.O_WRONLY
                    ),
                    0o600,
                )
            except FileExistsError as exc:
                if (
                    attempt == 0
                    and self._lock_is_stale()
                ):
                    try:
                        self.lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    except OSError as unlink_exc:
                        raise TaskRunLockError(
                            "无法清理过期任务锁："
                            f"{unlink_exc}"
                        ) from unlink_exc

                    continue

                raise TaskAlreadyRunningError(
                    "任务已经在运行，请不要重复启动："
                    + self._existing_lock_summary()
                ) from exc
            except OSError as exc:
                raise TaskRunLockError(
                    f"无法创建任务锁：{exc}"
                ) from exc

            payload = {
                "task_id": self.task_id,
                "token": self.token,
                "pid": os.getpid(),
                "started_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            try:
                with os.fdopen(
                    descriptor,
                    "w",
                    encoding="utf-8",
                ) as lock_file:
                    json.dump(
                        payload,
                        lock_file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    lock_file.write("\n")
            except Exception:
                self.lock_path.unlink(
                    missing_ok=True
                )
                raise

            self.acquired = True
            return

        raise TaskRunLockError(
            "无法取得任务锁"
        )

    def release(self) -> None:
        """仅释放由当前对象创建的锁。"""
        if not self.acquired:
            return

        try:
            payload = json.loads(
                self.lock_path.read_text(
                    encoding="utf-8"
                )
            )
        except FileNotFoundError:
            self.acquired = False
            return
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise TaskRunLockError(
                f"无法读取待释放任务锁：{exc}"
            ) from exc

        if payload.get("token") != self.token:
            raise TaskRunLockError(
                "任务锁已被其他进程替换，"
                "当前进程不会删除该锁"
            )

        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise TaskRunLockError(
                f"无法释放任务锁：{exc}"
            ) from exc
        finally:
            self.acquired = False

    def __enter__(self) -> "TaskRunLock":
        """进入上下文时取得锁。"""
        self.acquire()

        return self

    def __exit__(
        self,
        exc_type: type[
            BaseException
        ] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        """退出上下文时释放锁，不吞掉业务异常。"""
        del (
            exc_type,
            exc_value,
            traceback,
        )
        self.release()

        return False


def task_run_lock(
    task_id: str,
    *,
    lock_directory: str | Path | None = None,
    stale_after: timedelta = timedelta(
        hours=24
    ),
) -> TaskRunLock:
    """创建一个任务运行锁。"""
    return TaskRunLock(
        task_id=task_id,
        lock_directory=lock_directory,
        stale_after=stale_after,
    )
