# 完整智能分析链路

每次定时任务按以下顺序执行：

```text
真实政策搜索
→ 网页正文抓取
→ LLM 正式政策识别
→ LLM 新词新概念发现
→ 本地证据校验与历史基线评分
→ LLM 概念分析
→ LLM 广东电网六领域影响评估
→ LLM 生成两份候选回答
→ 稳定回答 ID
→ 七项指标评分与历史反馈重排
→ 知识治理任务
→ 单概念综合报告
→ 运行级 Markdown/JSON 智能简报
```

## 成本和规模控制

任务配置包含：

- `max_concepts_per_policy`：每份政策最多深入分析的概念数；
- `max_intelligence_items_per_run`：每次最多生成的完整情报项；
- `minimum_concept_confidence`：概念发现最低置信度；
- `minimum_novelty_score`：进入深入分析的最低新颖度。

默认值分别是 3、6、0.65、50。

## 证据边界

概念发现 Agent 提出的原文证据必须同时满足：

1. 证据句逐字存在于抓取正文；
2. 证据句包含候选术语。

未通过本地校验的候选不会进入后续分析。

## 输出

每次运行目录新增：

```text
intelligence_run.json
intelligence_brief.md
intelligence_brief.json
intelligence/
└── intelligence-xxxx/
    ├── concept_candidate.json
    ├── concept_analysis.json
    ├── business_impact.json
    ├── answer_package.json
    ├── feedback_ranking.json
    ├── governance_tasks.json
    └── integrated_report.md
```
