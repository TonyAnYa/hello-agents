@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHON="

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
)

if not defined PYTHON if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        "%VIRTUAL_ENV%\Scripts\python.exe" -c "import enterprise_concept_radar" >nul 2>&1
        if not errorlevel 1 set "PYTHON=%VIRTUAL_ENV%\Scripts\python.exe"
    )
)

if not defined PYTHON (
    python -c "import enterprise_concept_radar" >nul 2>&1
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo 尚未安装项目，请先运行 setup_windows.cmd
    pause
    exit /b 1
)

"%PYTHON%" scripts\validate_runtime_config.py
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

"%PYTHON%" scripts\run_scheduler.py
