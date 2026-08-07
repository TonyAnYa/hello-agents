#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

choose_project_python() {
    if [ -x ".venv/bin/python" ]; then
        printf '%s\n' ".venv/bin/python"
        return 0
    fi

    if [ -n "${VIRTUAL_ENV:-}" ] \
        && [ -x "${VIRTUAL_ENV}/bin/python" ]
    then
        if "${VIRTUAL_ENV}/bin/python" -c \
            'import enterprise_concept_radar' \
            >/dev/null 2>&1
        then
            printf '%s\n' "${VIRTUAL_ENV}/bin/python"
            return 0
        fi
    fi

    if command -v python >/dev/null 2>&1; then
        if python -c \
            'import enterprise_concept_radar' \
            >/dev/null 2>&1
        then
            command -v python
            return 0
        fi
    fi

    return 1
}

PYTHON="$(choose_project_python || true)"

if [ -z "$PYTHON" ]; then
    echo "尚未安装项目，请先运行："
    echo "./setup_macos.command"
    exit 1
fi

"$PYTHON" scripts/validate_runtime_config.py

echo
echo "EnterpriseConceptRadar 已启动"
echo "关闭 VS Code 不影响运行。"
echo "保持本终端和电脑处于运行状态。"
echo "按 Control+C 停止。"
echo

exec "$PYTHON" scripts/run_scheduler.py
