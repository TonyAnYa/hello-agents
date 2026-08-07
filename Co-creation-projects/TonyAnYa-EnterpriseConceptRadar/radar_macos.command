#!/bin/bash

cd "$(dirname "$0")" || exit 1

choose_project_python() {
    if [ -x ".venv/bin/python" ]; then
        printf '%s\n' ".venv/bin/python"
        return 0
    fi

    if (
        [ -n "${VIRTUAL_ENV:-}" ]
        && [ -x "${VIRTUAL_ENV}/bin/python" ]
    ); then
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
    read -r -p "按回车键退出。"
    exit 1
fi

pause_menu() {
    echo
    read -r -p "按回车键返回主菜单。"
}

while true; do
    clear
    echo "============================================================"
    echo " EnterpriseConceptRadar 运行菜单"
    echo "============================================================"
    echo "1. 查看当前状态（不联网）"
    echo "2. 立即输出一份简报"
    echo "3. 启动每日定时输出"
    echo "4. 修改每日定时输出时间"
    echo "5. 记录最近回答的用户反馈"
    echo "6. 配置本机 DeepSeek/SerpAPI Key"
    echo "7. 修改政策来源"
    echo "8. 修改高级追踪参数"
    echo "9. 运行正式配置自检（不联网）"
    echo "0. 退出"
    echo "============================================================"
    read -r -p "请选择 0-9：" choice

    case "$choice" in
        1)
            "$PYTHON" scripts/show_status.py
            pause_menu
            ;;
        2)
            echo
            echo "立即输出不受定时时间限制。"
            echo "本次会真实搜索并消耗 API 额度。"
            read -r -p "现在立即输出吗？[Y/n] " confirm
            confirm="${confirm:-Y}"
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                "$PYTHON" scripts/validate_runtime_config.py \
                    && "$PYTHON" scripts/run_tracking_task.py
            else
                echo "已取消。"
            fi
            pause_menu
            ;;
        3)
            "$PYTHON" scripts/validate_runtime_config.py
            if [ $? -eq 0 ]; then
                echo
                echo "每日定时输出已启动。"
                echo "关闭 VS Code 不影响；关闭本终端会停止。"
                echo "按 Control+C 返回菜单。"
                echo
                "$PYTHON" scripts/run_scheduler.py
            fi
            pause_menu
            ;;
        4)
            "$PYTHON" scripts/configure_schedule.py
            pause_menu
            ;;
        5)
            "$PYTHON" scripts/record_feedback.py
            pause_menu
            ;;
        6)
            "$PYTHON" scripts/configure_api_keys.py
            pause_menu
            ;;
        7)
            "$PYTHON" scripts/configure_policy_sources.py
            pause_menu
            ;;
        8)
            "$PYTHON" scripts/configure_tracking_task.py
            pause_menu
            ;;
        9)
            "$PYTHON" scripts/offline_self_check.py \
                --require-runtime
            pause_menu
            ;;
        0)
            echo "已退出。"
            exit 0
            ;;
        *)
            echo "无效选项。"
            pause_menu
            ;;
    esac
done
