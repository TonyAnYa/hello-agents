# EnterpriseConceptRadar 纯终端运行说明

## 运行条件

- Python 3.10、3.11 或 3.12；
- 可访问大模型服务和 SerpAPI；
- 电脑未关机，且未进入会停止网络和进程的深度休眠；
- 启动调度器的终端或命令提示符保持打开。

关闭 VS Code 不影响调度器。关闭运行调度器的终端窗口会停止程序。

## macOS

首次安装：

```bash
chmod +x setup_macos.command start_macos.command
./setup_macos.command
```

填写项目根目录 `.env`，然后启动：

```bash
./start_macos.command
```

## Windows

首次安装：

```bat
setup_windows.cmd
```

填写项目根目录 `.env`，然后启动：

```bat
start_windows.cmd
```

## 本地报告目录

默认配置为：

```text
~/Documents/EnterpriseConceptRadarReports
```

用户可通过 `configure_tracking_task.py` 改成其他绝对路径或项目相对路径。

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

其中 `intelligence_brief.md` 是面向用户的主要完整简报。

## 查看状态

macOS：

```bash
.venv/bin/python scripts/show_status.py
```

Windows：

```bat
.venv\Scripts\python.exe scripts\show_status.py
```

该命令不联网，不调用 SerpAPI 或模型。

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

程序会列出最近一次智能简报中的两种回答。用户可以选择：

- 专业；
- 一般；
- 不匹配；
- 采纳；
- 复制；
- 补充意见。

回答 ID 由政策、概念和回答风格稳定生成。下一次运行会把历史反馈接入第七项评分并重新排序。

## 并发保护

同一个任务同时只能运行一次。手动运行尚未结束时，定时调度不会再次启动该任务；反之亦然。

异常退出可能留下锁文件。锁超过 24 小时会被视为过期并自动清理。锁文件位于：

```text
data/runtime/tracking/locks/
```

## 修改任务

macOS：

```bash
.venv/bin/python scripts/configure_tracking_task.py
```

Windows：

```bat
.venv\Scripts\python.exe scripts\configure_tracking_task.py
```

输入相同任务 ID 会修改既有任务。
