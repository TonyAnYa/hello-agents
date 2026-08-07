#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

choose_python() {
    local candidate

    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c \
                'import sys; raise SystemExit(not ((3, 10) <= sys.version_info[:2] < (3, 13)))'
            then
                printf '%s\n' "$candidate"
                return 0
            fi
        fi
    done

    return 1
}

PYTHON_CMD="$(choose_python || true)"

if [ -z "$PYTHON_CMD" ]; then
    echo "未找到 Python 3.10、3.11 或 3.12。"
    echo "请先安装兼容版本的 Python。"
    exit 1
fi

echo "使用 Python：$PYTHON_CMD"

if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e .

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo
    echo "已创建 .env。"
    echo "请使用文本编辑器填写 LLM 和 SERPAPI 配置："
    echo "$(pwd)/.env"
fi

echo
read -r -p "现在配置政策来源吗？[Y/n] " configure_sources
configure_sources="${configure_sources:-Y}"

if [[ "$configure_sources" =~ ^[Yy]$ ]]; then
    .venv/bin/python scripts/configure_policy_sources.py
fi

echo
read -r -p "现在配置政策追踪任务吗？[Y/n] " configure_task
configure_task="${configure_task:-Y}"

if [[ "$configure_task" =~ ^[Yy]$ ]]; then
    .venv/bin/python scripts/configure_tracking_task.py
fi

echo
echo "安装与基础配置完成。"
echo "填写 .env 后运行："
echo "./start_macos.command"
