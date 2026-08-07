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
echo ============================================================
echo 安装完成
echo ============================================================
echo 以后只需要运行 radar_windows.cmd
echo 按菜单提示选择即可。
pause
exit /b 0

:error
echo.
echo 安装未完成，请查看上方提示后重新运行 setup_windows.cmd
pause
exit /b 1
