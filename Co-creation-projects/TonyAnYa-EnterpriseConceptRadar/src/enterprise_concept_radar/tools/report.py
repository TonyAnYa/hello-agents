"""概念发现 Markdown 报告工具。"""

from __future__ import annotations

from pathlib import Path

from enterprise_concept_radar.models import (
    AnswerPackage,
    BusinessImpactAssessment,
    ConceptAnalysis,
    ConceptCandidate,
    FeedbackAwareRankingResult,
    GovernanceTaskBatch,
    PolicyDocument,
)


def render_concept_discovery_report(
    document: PolicyDocument,
    candidates: list[ConceptCandidate],
) -> str:
    """将概念发现结果渲染成 Markdown。"""
    lines = [
        "# 能源政策概念发现报告",
        "",
        "## 文档信息",
        "",
        f"- **标题**：{document.title}",
        f"- **发布机构**：{document.source_name}",
        f"- **发布日期**：{document.published_date.isoformat()}",
        f"- **文件类型**：{document.document_type.value}",
        f"- **权威来源**：{document.source_url}",
        f"- **是否为教学模拟数据**：{document.is_simulated}",
        "",
    ]

    if document.is_simulated:
        lines.extend(
            [
                "> ⚠️ 本报告基于教学模拟政策生成，"
                "不得作为真实政策判断依据。",
                "",
            ]
        )

    lines.extend(
        [
            "## 发现摘要",
            "",
            f"本次共识别 **{len(candidates)}** 个候选概念。",
            "",
        ]
    )

    if not candidates:
        lines.extend(
            [
                "当前规则下未发现候选概念。",
                "",
            ]
        )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        first_seen = (
            candidate.first_seen_date.isoformat()
            if candidate.first_seen_date
            else "当前基线中未记录"
        )
        related_terms = (
            "、".join(candidate.related_terms)
            if candidate.related_terms
            else "暂无"
        )

        lines.extend(
            [
                f"## {index}. {candidate.term}",
                "",
                f"- **候选类型**：{candidate.candidate_type.value}",
                f"- **新颖度评分**：{candidate.novelty_score}/100",
                f"- **识别置信度**：{candidate.confidence:.0%}",
                f"- **基线最早记录**：{first_seen}",
                f"- **关联历史术语**：{related_terms}",
                "",
                "### 原文证据",
                "",
                f"> {candidate.evidence_quote}",
                "",
                "### 初步判断",
                "",
                candidate.explanation or "暂无解释。",
                "",
            ]
        )

    lines.extend(
        [
            "## 后续处理建议",
            "",
            "1. 使用权威历史语料核验首次出现时间。",
            "2. 检查政策正文是否给出正式定义。",
            "3. 与相近概念进行边界和政策语境辨析。",
            "4. 分析对广东电网业务和知识治理的影响。",
            "",
        ]
    )

    return "\n".join(lines)


def save_markdown_report(
    content: str,
    output_path: str | Path,
) -> Path:
    """以 UTF-8 编码保存 Markdown 报告。"""
    path = Path(output_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        content,
        encoding="utf-8",
    )

    return path
class IntegratedReportError(ValueError):
    """综合报告输入不一致或保存失败。"""


def _markdown_list(
    items: list[str],
    empty_text: str = "暂无",
) -> str:
    """将字符串列表转换为 Markdown 列表。"""
    if not items:
        return f"- {empty_text}"

    return "\n".join(
        f"- {item}"
        for item in items
    )


def _table_cell(value: object) -> str:
    """清理 Markdown 表格单元格内容。"""
    return (
        str(value)
        .replace("|", "\\|")
        .replace("\r\n", "<br>")
        .replace("\n", "<br>")
    )


def _format_counts(
    counts: dict[str, int],
) -> str:
    """将反馈统计字典转换为简短文本。"""
    active_counts = [
        f"{name}：{count}"
        for name, count in counts.items()
        if count > 0
    ]

    return "、".join(active_counts) or "无"


def validate_integrated_report_inputs(
    analysis: ConceptAnalysis,
    impact_assessment: BusinessImpactAssessment,
    answer_package: AnswerPackage,
    feedback_ranking: FeedbackAwareRankingResult,
    governance_batch: GovernanceTaskBatch,
) -> None:
    """校验综合报告的输入是否属于同一任务。"""
    terms = {
        analysis.term,
        impact_assessment.term,
        answer_package.term,
        feedback_ranking.ranking.term,
        governance_batch.term,
    }

    if len(terms) != 1:
        raise IntegratedReportError(
            "综合报告输入的 term 不一致"
        )

    source_document_ids = {
        analysis.source_document_id,
        impact_assessment.source_document_id,
        answer_package.source_document_id,
        feedback_ranking.ranking.source_document_id,
        governance_batch.source_document_id,
    }

    if len(source_document_ids) != 1:
        raise IntegratedReportError(
            "综合报告输入的来源文档不一致"
        )

    package_answer_ids = {
        candidate.answer_id
        for candidate in answer_package.candidates
    }
    ranking_answer_ids = {
        evaluation.answer_id
        for evaluation
        in feedback_ranking.ranking.evaluations
    }

    if package_answer_ids != ranking_answer_ids:
        raise IntegratedReportError(
            "回答包与排名结果的 answer_id 不一致"
        )


def build_integrated_report(
    analysis: ConceptAnalysis,
    impact_assessment: BusinessImpactAssessment,
    answer_package: AnswerPackage,
    feedback_ranking: FeedbackAwareRankingResult,
    governance_batch: GovernanceTaskBatch,
) -> str:
    """生成面向项目展示的综合 Markdown 报告。"""
    validate_integrated_report_inputs(
        analysis=analysis,
        impact_assessment=impact_assessment,
        answer_package=answer_package,
        feedback_ranking=feedback_ranking,
        governance_batch=governance_batch,
    )

    recommended_answer_id = (
        feedback_ranking.ranking.recommended_answer_id
    )
    recommended_candidate = next(
        candidate
        for candidate in answer_package.candidates
        if candidate.answer_id == recommended_answer_id
    )

    lines = [
        "# 企业大脑：新词新概念追踪综合报告",
        "",
        f"- **追踪概念：** {analysis.term}",
        (
            "- **来源文档 ID：** "
            f"{analysis.source_document_id}"
        ),
        (
            "- **数据性质：** "
            + (
                "教学模拟数据"
                if analysis.source_is_simulated
                else "正式来源数据"
            )
        ),
        (
            "- **当前推荐回答：** "
            f"{recommended_answer_id}"
        ),
        "",
        "## 一、管理摘要",
        "",
        impact_assessment.overall_summary,
        "",
        "### 推荐结论",
        "",
        feedback_ranking.ranking.recommendation_reason,
        "",
        "## 二、概念解释与证据边界",
        "",
        "### 概念解释草稿",
        "",
        analysis.explanation_draft,
        "",
        "### 政策原文事实",
        "",
        _markdown_list(analysis.source_facts),
        "",
        "### 规则判断",
        "",
        _markdown_list(analysis.rule_judgements),
        "",
        "### 模型推断",
        "",
        _markdown_list(analysis.model_inferences),
        "",
        "### 相关术语比较",
        "",
        _markdown_list(
            analysis.related_term_comparison
        ),
        "",
        "### 待核验事项",
        "",
        _markdown_list(analysis.uncertainties),
        "",
        "### 建议核验动作",
        "",
        _markdown_list(
            analysis.verification_actions
        ),
        "",
        "## 三、广东电网六领域影响评估",
        "",
        (
            "| 业务领域 | 影响程度 | "
            "影响摘要 | 建议行动 |"
        ),
        "|---|---:|---|---|",
    ]

    for impact in impact_assessment.domain_impacts:
        actions = "；".join(
            impact.recommended_actions
        ) or "暂无"

        lines.append(
            "| "
            f"{_table_cell(impact.domain.value)} | "
            f"{_table_cell(impact.impact_level.value)} | "
            f"{_table_cell(impact.impact_summary)} | "
            f"{_table_cell(actions)} |"
        )

    lines.extend(
        [
            "",
            "### 跨专业协同事项",
            "",
            _markdown_list(
                impact_assessment.cross_domain_issues
            ),
            "",
            "## 四、候选回答评分与推荐",
            "",
            (
                "| 回答 ID | 语义相关性 | 关键词覆盖 | "
                "权威依据 | 时效性 | 业务关联度 | "
                "可操作性 | 用户反馈 | 总分 |"
            ),
            (
                "|---|---:|---:|---:|---:|---:|"
                "---:|---:|---:|"
            ),
        ]
    )

    for evaluation in feedback_ranking.ranking.evaluations:
        lines.append(
            "| "
            f"{_table_cell(evaluation.answer_id)} | "
            f"{evaluation.semantic_relevance:.2f} | "
            f"{evaluation.keyword_coverage:.2f} | "
            f"{evaluation.authority_score:.2f} | "
            f"{evaluation.timeliness_score:.2f} | "
            f"{evaluation.business_relevance:.2f} | "
            f"{evaluation.actionability_score:.2f} | "
            f"{evaluation.user_feedback_score:.2f} | "
            f"{evaluation.total_score:.2f} |"
        )

    lines.extend(
        [
            "",
            "### 推荐回答",
            "",
            f"#### {recommended_candidate.title}",
            "",
            recommended_candidate.content,
            "",
            "#### 推荐回答的行动建议",
            "",
            _markdown_list(
                recommended_candidate.action_items
            ),
            "",
            "#### 推荐回答的限制说明",
            "",
            _markdown_list(
                recommended_candidate.caveats
            ),
            "",
            "## 五、用户反馈汇总",
            "",
            (
                "| 回答 ID | 反馈事件 | 评价统计 | "
                "行为统计 | 用户反馈分 |"
            ),
            "|---|---:|---|---|---:|",
        ]
    )

    for summary in feedback_ranking.feedback_summaries:
        lines.append(
            "| "
            f"{_table_cell(summary.answer_id)} | "
            f"{summary.total_events} | "
            f"{_table_cell(_format_counts(summary.rating_counts))} | "
            f"{_table_cell(_format_counts(summary.action_counts))} | "
            f"{summary.user_feedback_score:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 六、知识治理任务",
            "",
            (
                "| 优先级 | 任务类型 | 任务标题 | "
                "触发原因 | 关联回答 |"
            ),
            "|---|---|---|---|---|",
        ]
    )

    for task in governance_batch.tasks:
        lines.append(
            "| "
            f"{_table_cell(task.priority.value)} | "
            f"{_table_cell(task.task_type.value)} | "
            f"{_table_cell(task.title)} | "
            f"{_table_cell(task.trigger)} | "
            f"{_table_cell(task.related_answer_id or '无')} |"
        )

    lines.extend(
        [
            "",
            "## 七、使用声明",
            "",
        ]
    )

    if analysis.source_is_simulated:
        lines.extend(
            [
                (
                    "> 当前来源为教学模拟数据，"
                    "不能作为真实政策依据。"
                ),
                ">",
                (
                    "> 本报告中的概念解释、业务影响、"
                    "回答推荐和治理任务均用于课程演示，"
                    "正式使用前必须核验权威政策原文。"
                ),
            ]
        )
    else:
        lines.append(
            "> 本报告仍需由相关专业人员复核后使用。"
        )

    lines.append("")

    return "\n".join(lines)


def save_integrated_report(
    report: str,
    output_path: str | Path,
) -> Path:
    """将综合报告保存为 UTF-8 Markdown 文件。"""
    path = Path(output_path)

    try:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            report,
            encoding="utf-8",
        )
    except OSError as exc:
        raise IntegratedReportError(
            f"无法保存综合报告：{path}；{exc}"
        ) from exc

    return path