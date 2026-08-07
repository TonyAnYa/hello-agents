# EnterpriseConceptRadar 客户终端使用说明

## 首次安装

macOS：

```bash
./setup_macos.command
```

Windows：

```bat
setup_windows.cmd
```

客户不需要手动运行 Python 脚本。

## 立即输出

打开运行菜单：

macOS：

```bash
./radar_macos.command
```

Windows：

```bat
radar_windows.cmd
```

选择：

```text
2. 立即输出一份简报
```

回答：

```text
现在立即输出吗？[Y/n]
```

选择 `Y` 或直接回车，程序马上执行。立即输出不等待任何定时时间。

## 修改定时输出

在运行菜单选择：

```text
4. 修改每日定时输出时间
```

流程：

```text
启用每天定时输出吗？[Y/n]
→ 保留当前时间吗？[Y/n]
→ 或恢复 08:30、14:00
→ 或输入自己的 HH:MM 时间
```

示例：

```text
09:00
09:00,17:30
07:45,12:00,18:15
```

设置保存后，选择菜单第 3 项启动调度器。

## 定时输出与立即输出的关系

```text
立即输出：现在马上运行一次
定时输出：在设置的每日时间运行
```

关闭定时输出不会禁用立即输出。

## 查看结果

主要阅读文件：

```text
<输出目录>/<任务 ID>/latest/intelligence_brief.md
```
