"""概念发现 Markdown 报告工具。"""

from __future__ import annotations

from pathlib import Path

from enterprise_concept_radar.models import (
    ConceptCandidate,
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
