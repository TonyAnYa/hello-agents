# EnterpriseConceptRadar 纯终端运行说明

## 运行条件

- Python 3.10、3.11 或 3.12；
- 可访问大模型服务和 SerpAPI；
- 电脑未关机、未进入会停止网络和进程的深度休眠；
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

用户可在 `configure_tracking_task.py` 中改成其他绝对路径或项目相对路径。

输出结构：

```text
用户选择的目录/
└── task_id/
    ├── YYYY-MM-DD/
    │   └── HHMMSS/
    │       ├── policy_brief.md
    │       ├── policy_brief.json
    │       ├── collection_run.json
    │       ├── delivery_receipts.json
    │       ├── documents/
    │       └── raw_pages/
    └── latest/
        ├── policy_brief.md
        ├── policy_brief.json
        ├── collection_run.json
        └── delivery_receipts.json
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

输入相同任务 ID 会修改既有任务，而不是新建重复任务。
