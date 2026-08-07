"""测试真实运行概念历史与动态基线。"""

from datetime import date, datetime, timezone
from types import SimpleNamespace

from enterprise_concept_radar.concept_history import (
    ConceptHistoryStore,
    merge_baseline_with_history,
    record_intelligence_history,
)
from enterprise_concept_radar.models import (
    BaselineTerm,
    ConceptBaseline,
    ConceptCandidate,
    ConceptCandidateType,
    PolicyDocument,
    PolicyDocumentType,
)
from enterprise_concept_radar.scoring.novelty import (
    assess_term_novelty,
)


def test_runtime_history_becomes_effective_baseline(
    tmp_path,
) -> None:
    """真实运行中已见术语下一次不能继续算首次新增。"""
    document = PolicyDocument(
        document_id="doc-1",
        title="电力安全生产行动计划",
        source_name="国家能源局",
        source_url="https://example.com/policy",
        published_date=date(2026, 8, 7),
        document_type=PolicyDocumentType.PLAN,
        content=(
            "这是足够长度的真实政策正文，"
            "用于测试概念历史记录。"
        ),
    )
    candidate = ConceptCandidate(
        term="人工智能+电力应急",
        source_document_id="doc-1",
        evidence_quote="人工智能+电力应急",
        candidate_type=ConceptCandidateType.NEW_CONCEPT,
        novelty_score=92,
        confidence=0.9,
        detected_at=datetime(
            2026,
            8,
            7,
            tzinfo=timezone.utc,
        ),
    )
    item = SimpleNamespace(
        document_id="doc-1",
        policy_title=document.title,
        policy_source_name=document.source_name,
        policy_source_url=str(document.source_url),
        candidate=candidate,
    )
    collection = SimpleNamespace(documents=[document])
    intelligence = SimpleNamespace(
        intelligence_items=[item]
    )
    history_path = tmp_path / "history.json"

    history = record_intelligence_history(
        task_id="energy-policy-radar",
        collection_run=collection,
        intelligence_run=intelligence,
        path=history_path,
    )
    baseline = ConceptBaseline(
        baseline_name="测试基线",
        version="1",
        known_terms=[
            BaselineTerm(
                term="新型电力系统",
                first_seen_date=date(2021, 3, 1),
            )
        ],
    )
    effective = merge_baseline_with_history(
        baseline=baseline,
        history=history,
    )
    result = assess_term_novelty(
        "人工智能+电力应急",
        effective,
    )

    assert result.score == 25
    assert result.candidate_type == (
        ConceptCandidateType.HEATING_CONCEPT
    )
    assert result.first_seen_date == date(2026, 8, 7)


def test_empty_history_does_not_change_seed_terms() -> None:
    """空运行历史不得破坏静态基线。"""
    baseline = ConceptBaseline(
        baseline_name="测试基线",
        version="1",
        known_terms=[BaselineTerm(term="绿电直连")],
    )
    effective = merge_baseline_with_history(
        baseline=baseline,
        history=ConceptHistoryStore(task_id="task-1"),
    )

    assert len(effective.known_terms) == 1
    assert effective.known_terms[0].term == "绿电直连"
