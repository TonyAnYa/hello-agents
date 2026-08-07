"""测试概念历史核验提示文案。"""

from enterprise_concept_radar.intelligence_pipeline import (
    describe_candidate_history,
)
from enterprise_concept_radar.models import (
    ConceptCandidate,
    ConceptCandidateType,
)


def test_unverified_new_concept_is_not_called_first_ever() -> None:
    """未命中本地基线时必须明确仍待历史语料核验。"""
    candidate = ConceptCandidate(
        term="测试新概念",
        source_document_id="doc-1",
        evidence_quote="测试新概念",
        candidate_type=ConceptCandidateType.NEW_CONCEPT,
        novelty_score=92,
        confidence=0.9,
    )

    text = describe_candidate_history(candidate)

    assert "本地历史基线" in text
    assert "不能据此断言政策首次提出" in text
