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

echo "正在安装 EnterpriseConceptRadar……"
echo "使用 Python：$PYTHON_CMD"

if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e .

chmod +x \
    setup_macos.command \
    start_macos.command \
    radar_macos.command

echo
.venv/bin/python scripts/configure_api_keys.py

echo
.venv/bin/python scripts/customer_setup.py

echo
.venv/bin/python scripts/offline_self_check.py \
    --require-runtime

echo
echo "============================================================"
echo "安装完成"
echo "============================================================"
echo "以后只需要运行："
echo "./radar_macos.command"
echo
echo "按菜单提示选择即可。"
