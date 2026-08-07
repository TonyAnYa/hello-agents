#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "尚未安装项目，请先运行："
    echo "./setup_macos.command"
    exit 1
fi

.venv/bin/python scripts/validate_runtime_config.py

echo
echo "EnterpriseConceptRadar 已启动"
echo "关闭 VS Code 不影响运行。"
echo "保持本终端和电脑处于运行状态。"
echo "按 Control+C 停止。"
echo

exec .venv/bin/python scripts/run_scheduler.py
