@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="

py -3.12 -c "import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.12"

if not defined PYTHON_CMD (
    py -3.11 -c "import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)

if not defined PYTHON_CMD (
    py -3.10 -c "import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py -3.10"
)

if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(not ((3,10) <= sys.version_info[:2] < (3,13)))" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo 未找到 Python 3.10、3.11 或 3.12。
    echo 请先安装兼容版本的 Python。
    pause
    exit /b 1
)

echo 正在安装 EnterpriseConceptRadar……
echo 使用 Python：%PYTHON_CMD%

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :error

echo.
.venv\Scripts\python.exe scripts\configure_api_keys.py
if errorlevel 1 goto :error

echo.
.venv\Scripts\python.exe scripts\customer_setup.py
if errorlevel 1 goto :error

echo.
.venv\Scripts\python.exe scripts\offline_self_check.py --require-runtime
if errorlevel 1 goto :error

echo.
set /p RUN_NOW=现在立即生成第一份简报吗？[Y/n]
if "%RUN_NOW%"=="" set "RUN_NOW=Y"

if /I "%RUN_NOW%"=="Y" (
    echo.
    echo 正在立即搜索政策并生成简报……
    .venv\Scripts\python.exe scripts\validate_runtime_config.py
    if errorlevel 1 goto :error
    .venv\Scripts\python.exe scripts\run_tracking_task.py
    if errorlevel 1 goto :error
) else (
    echo 已跳过立即输出。
)

echo.
echo ============================================================
echo 安装完成
echo ============================================================
echo 以后只需要运行 radar_windows.cmd
echo 菜单中的“立即输出”会马上执行，不受每日定时时间限制。
pause
exit /b 0

:error
echo.
echo 安装未完成，请查看上方提示后重新运行 setup_windows.cmd
pause
exit /b 1
