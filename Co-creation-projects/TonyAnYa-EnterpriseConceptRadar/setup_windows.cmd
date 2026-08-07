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

echo 使用 Python：%PYTHON_CMD%

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :error

if not exist ".env" (
    copy /Y ".env.example" ".env" >nul
    echo.
    echo 已创建 .env。
    echo 请使用记事本填写 LLM 和 SERPAPI 配置：
    echo %CD%\.env
)

echo.
set /p CONFIGURE_SOURCES=现在配置政策来源吗？[Y/n] 
if "%CONFIGURE_SOURCES%"=="" set "CONFIGURE_SOURCES=Y"
if /I "%CONFIGURE_SOURCES%"=="Y" (
    .venv\Scripts\python.exe scripts\configure_policy_sources.py
    if errorlevel 1 goto :error
)

echo.
set /p CONFIGURE_TASK=现在配置政策追踪任务吗？[Y/n] 
if "%CONFIGURE_TASK%"=="" set "CONFIGURE_TASK=Y"
if /I "%CONFIGURE_TASK%"=="Y" (
    .venv\Scripts\python.exe scripts\configure_tracking_task.py
    if errorlevel 1 goto :error
)

echo.
echo 安装与基础配置完成。
echo 填写 .env 后运行 start_windows.cmd
pause
exit /b 0

:error
echo.
echo 安装或配置失败，请查看上方错误。
pause
exit /b 1
