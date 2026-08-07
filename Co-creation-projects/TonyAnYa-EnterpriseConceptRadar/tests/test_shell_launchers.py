"""测试 macOS Bash 启动器语法。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MACOS_LAUNCHERS = [
    "setup_macos.command",
    "radar_macos.command",
    "start_macos.command",
]


@pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="当前平台没有 bash",
)
@pytest.mark.parametrize(
    "launcher_name",
    MACOS_LAUNCHERS,
)
def test_macos_launcher_has_valid_bash_syntax(
    launcher_name: str,
) -> None:
    """所有 macOS 启动器都必须通过 bash -n。"""
    result = subprocess.run(
        [
            "bash",
            "-n",
            str(PROJECT_ROOT / launcher_name),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
