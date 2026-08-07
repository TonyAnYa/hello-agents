@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo 尚未安装项目，请先运行 setup_windows.cmd
    pause
    exit /b 1
)

.venv\Scripts\python.exe scripts\validate_runtime_config.py
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo EnterpriseConceptRadar 已启动
echo 关闭 VS Code 不影响运行。
echo 保持本命令提示符窗口和电脑处于运行状态。
echo 按 Control+C 停止。
echo.

.venv\Scripts\python.exe scripts\run_scheduler.py
