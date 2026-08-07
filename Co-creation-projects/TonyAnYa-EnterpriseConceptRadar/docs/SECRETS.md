# API Key 客户设置与安全边界

## 首次安装

客户只运行一个安装文件：

macOS：

```bash
./setup_macos.command
```

Windows：

```bat
setup_windows.cmd
```

安装程序自动进入 API 设置，不要求客户手动执行 Python 命令。

## 可见输入

根据客户核对需求，Key 输入时会显示字符。

流程：

```text
输入 DeepSeek API Key
→ 屏幕完整显示
→ Y/N 确认
→ 输入 SerpAPI API Key
→ 屏幕完整显示
→ Y/N 确认
→ Y/N 确认保存
```

填写时应：

- 确保周围没有无关人员；
- 不截图；
- 不录屏；
- 不把终端内容复制到聊天或邮件；
- 使用完成后可清屏或关闭终端。

输入内容不会进入 shell 命令历史，因为它是程序读取的交互输入，而不是终端命令。

## 本地保存

Key 保存到当前电脑项目根目录的：

```text
.env
```

该文件不会进入 Git 或发行 ZIP。

## 发行防泄露

发行构建执行：

```text
排除 .env
排除 data/runtime
排除用户报告与网页快照
扫描待打包文件中的本机秘密值
生成 ZIP
再次扫描 ZIP
```

发现问题时只显示变量名和文件名，不显示 Key 内容。

## 重新配置

客户可在运行菜单中选择：

```text
安全配置本机 DeepSeek/SerpAPI Key
```

已有配置默认保留。选择重新配置后，新输入的 Key 会显示并要求 Y/N 确认。
