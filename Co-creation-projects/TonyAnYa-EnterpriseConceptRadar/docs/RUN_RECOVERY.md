# 运行失败、零结果和恢复

## “搜索成功但候选为 0”不再静默通过

旧搜索实现把全部关键词和整段用户问题同时加入一条 Google 查询，可能导致查询过窄。SerpAPI JSON 中的 `error` 也可能在 HTTP 成功时出现，旧实现没有检查该字段。

当前实现：

```text
政策文种 + OR 主题词 + 来源 + 日期范围
→ 零结果时使用主题词宽查询
→ 两条查询都保留来源和日期范围
→ 检查 search_metadata.status
→ 检查顶层 error
→ 全部零结果时写入采集异常
→ 所有来源都失败时整次任务失败
```

因此不会再把搜索服务错误或异常零结果记录成“无异常成功”。

## 外部虚拟环境

开发者可以把虚拟环境放在项目目录外。macOS 和 Windows 启动脚本按顺序查找：

```text
项目内 .venv
→ 当前已激活的 VIRTUAL_ENV
→ 当前 python 且能导入项目包
```

三者都不可用时，才提示运行安装脚本。

## 失败后重试

修复配置或网络问题后重新执行一次即可。不要手工删除状态文件，36 小时重叠窗口会覆盖最近运行边界。

## 不启动调度器的验收

开发阶段执行：

```bash
python scripts/validate_runtime_config.py
python scripts/run_tracking_task.py
python scripts/show_status.py
```

正式客户使用运行菜单的“立即运行一次”。
