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

:menu
cls
echo ============================================================
echo  EnterpriseConceptRadar 运行菜单
echo ============================================================
echo 1. 查看当前状态（不联网）
echo 2. 立即运行一次（真实联网并消耗 API 额度）
echo 3. 持续启动定时调度器
echo 4. 记录最近回答的用户反馈
echo 5. 安全配置本机 DeepSeek/SerpAPI Key
echo 6. 修改政策来源
echo 7. 修改追踪任务和简报目录
echo 8. 运行正式配置自检（不联网）
echo 9. 退出
echo ============================================================
set /p CHOICE=请选择 1-9：

if "%CHOICE%"=="1" goto status
if "%CHOICE%"=="2" goto runonce
if "%CHOICE%"=="3" goto scheduler
if "%CHOICE%"=="4" goto feedback
if "%CHOICE%"=="5" goto apikeys
if "%CHOICE%"=="6" goto sources
if "%CHOICE%"=="7" goto task
if "%CHOICE%"=="8" goto check
if "%CHOICE%"=="9" goto end

echo 无效选项。
pause
goto menu

:status
"%PYTHON%" scripts\show_status.py
pause
goto menu

:runonce
echo.
echo 即将真实搜索网页并调用大模型。
set /p CONFIRM=确认立即运行？[y/N] 
if /I not "%CONFIRM%"=="Y" (
    echo 已取消。
    pause
    goto menu
)
"%PYTHON%" scripts\validate_runtime_config.py
if errorlevel 1 (
    pause
    goto menu
)
"%PYTHON%" scripts\run_tracking_task.py
pause
goto menu

:scheduler
"%PYTHON%" scripts\validate_runtime_config.py
if errorlevel 1 (
    pause
    goto menu
)
echo.
echo 调度器将在本命令提示符窗口持续运行。
echo 关闭 VS Code 不影响；关闭本窗口会停止。
echo 按 Control+C 停止并返回菜单。
echo.
"%PYTHON%" scripts\run_scheduler.py
pause
goto menu

:feedback
"%PYTHON%" scripts\record_feedback.py
pause
goto menu

:apikeys
"%PYTHON%" scripts\configure_api_keys.py
pause
goto menu

:sources
"%PYTHON%" scripts\configure_policy_sources.py
pause
goto menu

:task
"%PYTHON%" scripts\configure_tracking_task.py
pause
goto menu

:check
"%PYTHON%" scripts\offline_self_check.py --require-runtime
pause
goto menu

:end
echo 已退出。
exit /b 0
