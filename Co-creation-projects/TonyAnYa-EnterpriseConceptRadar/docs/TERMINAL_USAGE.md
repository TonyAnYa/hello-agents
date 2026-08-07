# EnterpriseConceptRadar 纯终端运行说明

## 重要运行规则

关闭 VS Code 不影响程序。关闭正在运行调度器的终端或命令提示符窗口会停止程序。电脑关机或进入会停止网络和进程的深度休眠后，程序也会停止。

重新开机后再次运行启动脚本即可恢复。系统会根据上次成功时间和重叠检索窗口继续搜索。

## macOS

首次安装：

```bash
chmod +x setup_macos.command start_macos.command radar_macos.command
./setup_macos.command
```

打开操作菜单：

```bash
./radar_macos.command
```

绕过菜单，直接持续调度：

```bash
./start_macos.command
```

## Windows

首次安装：

```bat
setup_windows.cmd
```

打开操作菜单：

```bat
radar_windows.cmd
```

绕过菜单，直接持续调度：

```bat
start_windows.cmd
```

## 菜单功能

```text
1 查看当前状态
2 立即真实运行一次
3 持续启动定时调度器
4 记录最近回答的用户反馈
5 修改政策来源
6 修改追踪任务和简报目录
7 运行正式配置自检
8 退出
```

选项 1 和 7 不访问网络。选项 2 和 3 会真实调用搜索服务和大模型。

## 简报目录

首次配置时由用户指定。默认：

```text
~/Documents/EnterpriseConceptRadarReports
```

每次运行目录包含：

```text
policy_brief.md
policy_brief.json
collection_run.json
intelligence_brief.md
intelligence_brief.json
intelligence_run.json
delivery_receipts.json
documents/
raw_pages/
intelligence/
```

主要阅读文件是 `intelligence_brief.md`。`latest` 目录保存最近一次成功运行的关键结果。

## 查看状态

macOS：

```bash
.venv/bin/python scripts/show_status.py
```

Windows：

```bat
.venv\Scripts\python.exe scripts\show_status.py
```

## 记录回答反馈

完成至少一次正式运行后：

macOS：

```bash
.venv/bin/python scripts/record_feedback.py
```

Windows：

```bat
.venv\Scripts\python.exe scripts\record_feedback.py
```

下一次运行会把历史反馈接入第七项评分。

## 离线自检

基础安装检查：

```bash
python scripts/offline_self_check.py
```

正式运行配置检查：

```bash
python scripts/offline_self_check.py --require-runtime
```

自检不会访问网络，也不会输出秘密值。

## 同一任务并发保护

手动运行和定时运行不能同时启动同一任务。第二个进程会退出，避免重复消耗 API 额度。异常遗留锁超过 24 小时后会自动清理。
