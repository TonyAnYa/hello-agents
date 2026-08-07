# EnterpriseConceptRadar

EnterpriseConceptRadar 使用 DeepSeek 大模型和 SerpAPI 搜索真实能源政策，发现新词、新概念和制度安排，分析其对广东电网的影响，并生成本地 Markdown/JSON 智能简报。

## 客户只需要运行一个安装文件

发行压缩包不包含任何人的 API Key。

### macOS

解压后打开终端，进入文件夹，只运行：

```bash
./setup_macos.command
```

### Windows

解压后打开命令提示符，进入文件夹，只运行：

```bat
setup_windows.cmd
```

安装脚本会自动完成：

```text
安装程序
→ 填写本机 DeepSeek API Key
→ Y/N 核对
→ 填写本机 SerpAPI API Key
→ Y/N 核对
→ Y/N 选择是否启用全网搜索
→ Y/N 使用推荐简报目录
→ 自动生成推荐任务
→ 离线检查
```

不需要客户手动运行 Python 命令。

## API Key 输入方式

首次安装时，DeepSeek 和 SerpAPI Key 会直接显示在屏幕上，方便客户核对。

每个 Key 输入后只需要回答：

```text
确认填写正确吗？[Y/n]
```

选择 `Y` 或直接回车表示正确；选择 `N` 重新填写。

因为 Key 会显示在屏幕上，填写时应确保周围没有无关人员，也不要截图或录屏。

Key 只写入当前电脑的 `.env`。发行程序会强制排除 `.env`，并扫描其他待打包文件，防止开发者 Key 被误发给客户。

## 推荐初始设置

安装向导自动使用：

```text
大模型：DeepSeek
模型：deepseek-chat
API 地址：https://api.deepseek.com
政策来源：国家能源局、国家发展改革委
运行时间：每天北京时间 08:30、14:00
简报位置：~/Documents/EnterpriseConceptRadarReports
```

客户只需用 Y/N 决定：

```text
是否同时启用全网搜索
是否使用推荐简报位置
是否确认应用设置
```

选择不使用推荐简报位置时，才需要输入自己的目录。

## 安装完成后的使用

macOS：

```bash
./radar_macos.command
```

Windows：

```bat
radar_windows.cmd
```

菜单提供查看状态、立即运行、持续调度、反馈、修改来源、修改任务和检查配置等功能。

关闭 VS Code 不影响程序。持续调度时需要保持启动调度器的终端或命令提示符窗口打开。

## 主要输出

```text
<简报目录>/<任务 ID>/latest/intelligence_brief.md
<简报目录>/<任务 ID>/latest/intelligence_brief.json
```

## 密钥安全

最终压缩包会排除：

```text
.env
.venv
data/runtime
客户简报
网页快照
本地日志
Git 元数据
```

打包前和打包后都会扫描本机 Key 是否误出现在其他文件中。发现泄露风险时，发行包不会生成。

更多说明见：

```text
docs/SECRETS.md
docs/TERMINAL_USAGE.md
docs/RELEASE.md
```
