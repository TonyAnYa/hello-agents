"""测试概念发现工作流的核心组件。"""

from enterprise_concept_radar.config import (
    BASELINE_DATA_DIR,
    CONFIG_DIR,
    SAMPLE_POLICY_DIR,
)
from enterprise_concept_radar.models import (
    ConceptCandidateType,
)
from enterprise_concept_radar.scoring import (
    load_concept_baseline,
)
from enterprise_concept_radar.tools import (
    extract_concept_candidates,
    load_concept_rules,
    load_policy_directory,
    render_concept_discovery_report,
)


def test_sample_policy_concept_discovery() -> None:
    """教学样本应发现新增说法和已有升温概念。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
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

    terms = {
        candidate.term
        for candidate in candidates
    }

    assert "多用户绿电直连" in terms
    assert "绿电直连" in terms
    assert "协同机制" not in terms
    assert "市场交易" not in terms

    candidate_by_term = {
        candidate.term: candidate
        for candidate in candidates
    }

    assert (
        candidate_by_term[
            "多用户绿电直连"
        ].candidate_type
        == ConceptCandidateType.NEW_EXPRESSION
    )
    assert (
        candidate_by_term[
            "绿电直连"
        ].candidate_type
        == ConceptCandidateType.HEATING_CONCEPT
    )


def test_report_contains_evidence_and_warning() -> None:
    """模拟数据报告应包含证据和醒目提示。"""
    document = load_policy_directory(
        SAMPLE_POLICY_DIR
    )[0]
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

    report = render_concept_discovery_report(
        document=document,
        candidates=candidates,
    )

    assert "教学模拟政策" in report
    assert "多用户绿电直连" in report
    assert "原文证据" in report
    assert "新增说法" in report