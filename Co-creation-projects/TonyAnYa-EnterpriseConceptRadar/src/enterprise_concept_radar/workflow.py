"""EnterpriseConceptRadar 业务工作流。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    CONFIG_DIR,
    REPORT_DIR,
    SAMPLE_POLICY_DIR,
)
from enterprise_concept_radar.models import (
    ConceptCandidate,
    PolicyDocument,
)
from enterprise_concept_radar.scoring import (
    load_concept_baseline,
)
from enterprise_concept_radar.tools import (
    extract_concept_candidates,
    load_concept_rules,
    load_policy_directory,
    render_concept_discovery_report,
    save_markdown_report,
)


@dataclass(frozen=True, slots=True)
class ConceptDiscoveryResult:
    """概念发现工作流执行结果。"""

    document: PolicyDocument
    candidates: tuple[ConceptCandidate, ...]
    report_path: Path


def run_demo_concept_discovery() -> ConceptDiscoveryResult:
    """运行教学政策样本的概念发现工作流。"""
    documents = load_policy_directory(
        SAMPLE_POLICY_DIR
    )

    if not documents:
        raise RuntimeError(
            f"政策样本目录中没有 JSON 文件：{SAMPLE_POLICY_DIR}"
        )

    document = documents[0]

    baseline = load_concept_baseline(
        BASELINE_DATA_DIR / "known_terms.json"
    )
    rules = load_concept_rules(
        CONFIG_DIR / "concept_rules.yaml"
    )

    candidates = extract_concept_candidates(
        document=document,
        baseline=baseline,
        rules=rules,
    )

    report_content = render_concept_discovery_report(
        document=document,
        candidates=candidates,
    )
    report_path = save_markdown_report(
        content=report_content,
        output_path=(
            REPORT_DIR
            / "demo_concept_discovery.md"
        ),
    )

    return ConceptDiscoveryResult(
        document=document,
        candidates=tuple(candidates),
        report_path=report_path,
    )