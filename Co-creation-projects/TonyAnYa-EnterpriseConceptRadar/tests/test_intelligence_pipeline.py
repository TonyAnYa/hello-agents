"""测试真实政策到完整智能分析报告的工作流。"""

from datetime import date, datetime, timezone

from enterprise_concept_radar.intelligence_pipeline import (
    calculate_timeliness_score,
    run_policy_intelligence,
    save_policy_intelligence_run,
    stabilize_answer_package_ids,
)
from enterprise_concept_radar.models import (
    AnswerCandidate,
    AnswerPackage,
    AnswerStyle,
    BusinessDomain,
    BusinessDomainImpact,
    BusinessImpactAssessment,
    ConceptAnalysis,
    ConceptBaseline,
    ConceptCandidate,
    ConceptCandidateType,
    ImpactLevel,
    PolicyDocument,
    PolicyDocumentType,
)
from enterprise_concept_radar.policy_collection import (
    PolicyCollectionRun,
)
from enterprise_concept_radar.tools.concept_extractor import (
    ConceptRules,
)
from enterprise_concept_radar.tracking_tasks import (
    TrackingTask,
)


def build_document() -> PolicyDocument:
    """创建在线真实政策。"""
    return PolicyDocument(
        document_id="online-policy-1",
        title="关于推进多主体绿电直连的通知",
        source_name="国家能源局",
        source_url=(
            "https://example.com/policy"
        ),
        published_date=date(2026, 8, 7),
        document_type=(
            PolicyDocumentType.NOTICE
        ),
        content=(
            "关于推进多主体绿电直连的通知。\n"
            "探索多主体绿电直连协同结算机制，"
            "完善项目接入和市场交易规则。\n"
            "本通知自发布之日起实施。"
        ),
        is_simulated=False,
    )


def build_candidate() -> ConceptCandidate:
    """创建概念候选。"""
    return ConceptCandidate(
        term="多主体绿电直连",
        source_document_id="online-policy-1",
        evidence_quote=(
            "探索多主体绿电直连协同结算机制，"
            "完善项目接入和市场交易规则。"
        ),
        candidate_type=(
            ConceptCandidateType.NEW_EXPRESSION
        ),
        novelty_score=82,
        confidence=0.94,
    )


def fake_discover(**kwargs):
    """替代概念发现 LLM。"""
    return [build_candidate()]


def fake_analyze(**kwargs):
    """替代概念分析 LLM。"""
    candidate = kwargs["candidate"]

    return ConceptAnalysis(
        term=candidate.term,
        source_document_id=(
            candidate.source_document_id
        ),
        source_is_simulated=False,
        explanation_draft=(
            "多主体绿电直连是对绿电直连参与主体"
            "和协同机制的扩展性政策表述。"
        ),
        source_facts=[
            candidate.evidence_quote,
        ],
        rule_judgements=[
            "与既有绿电直连存在包含关系。"
        ],
        model_inferences=[
            "可能增加交易与结算协同要求。"
        ],
        related_term_comparison=[
            "相比绿电直连，强调多主体协同。"
        ],
        uncertainties=[
            "适用主体范围仍需核验。"
        ],
        verification_actions=[
            "核验正式实施细则。"
        ],
        confidence=0.86,
    )


def fake_impact(**kwargs):
    """替代业务影响 LLM。"""
    analysis = kwargs["analysis"]

    return BusinessImpactAssessment(
        term=analysis.term,
        source_document_id=(
            analysis.source_document_id
        ),
        source_is_simulated=False,
        overall_summary=(
            "可能影响市场交易、计量结算和项目接入协同。"
        ),
        domain_impacts=[
            BusinessDomainImpact(
                domain=BusinessDomain.MARKET,
                impact_level=ImpactLevel.HIGH,
                impact_summary=(
                    "需要研究多主体交易组织方式。"
                ),
                recommended_actions=[
                    "开展交易规则专题评估。"
                ],
            )
        ],
        cross_domain_issues=[
            "市场、计量与规划专业协同。"
        ],
        governance_tasks=[
            "建立多主体绿电直连概念词条"
        ],
        uncertainties=[
            "结算边界仍需核验。"
        ],
        confidence=0.82,
    )


def fake_compose(**kwargs):
    """替代双回答生成 LLM。"""
    analysis = kwargs["analysis"]

    return AnswerPackage(
        question=kwargs["question"],
        term=analysis.term,
        source_document_id=(
            analysis.source_document_id
        ),
        source_is_simulated=False,
        candidates=[
            AnswerCandidate(
                answer_id="temporary-a",
                style=(
                    AnswerStyle.EXECUTIVE_BRIEF
                ),
                title="管理摘要",
                content=(
                    "多主体绿电直连可能对市场交易形成"
                    "较高影响，建议开展规则专题评估。"
                ),
                evidence_references=[
                    "政策原文"
                ],
                action_items=[
                    "开展交易规则专题评估"
                ],
            ),
            AnswerCandidate(
                answer_id="temporary-b",
                style=(
                    AnswerStyle.PROFESSIONAL_ANALYSIS
                ),
                title="专业分析",
                content=(
                    "该概念扩展了绿电直连的参与主体，"
                    "需要从市场交易、计量结算和规划建设"
                    "等方面继续开展专业核验。"
                ),
                evidence_references=[
                    "政策原文"
                ],
                action_items=[
                    "核验适用主体和结算边界"
                ],
            ),
        ],
    )


def build_collection_run() -> PolicyCollectionRun:
    """创建已完成真实采集的运行结果。"""
    now = datetime(
        2026,
        8,
        7,
        1,
        0,
        tzinfo=timezone.utc,
    )

    return PolicyCollectionRun(
        task_id="energy-policy-radar",
        run_id="collection-1",
        started_at=now,
        completed_at=now,
        published_after=date(2026, 8, 1),
        published_before=date(2026, 8, 7),
        documents=[build_document()],
        document_fingerprints=["fingerprint"],
        searched_candidate_count=1,
        fetched_page_count=1,
        llm_call_count=1,
        duplicate_count=0,
        previously_delivered_count=0,
    )


def build_task() -> TrackingTask:
    """创建智能分析任务。"""
    return TrackingTask(
        task_id="energy-policy-radar",
        name="能源政策追踪",
        question="该政策对广东电网有什么影响？",
        keywords=["绿电直连"],
        max_concepts_per_policy=3,
        max_intelligence_items_per_run=6,
    )


def test_full_intelligence_pipeline_and_save(
    tmp_path,
) -> None:
    """应串联分析、影响、回答、评分、治理和报告。"""
    run = run_policy_intelligence(
        task=build_task(),
        collection_run=build_collection_run(),
        baseline=ConceptBaseline(
            baseline_name="test",
            version="1",
            known_terms=[],
        ),
        rules=ConceptRules(
            minimum_term_length=2,
            maximum_candidates=3,
            ignored_terms=frozenset(),
        ),
        feedback_events=[],
        discover_func=fake_discover,
        analyze_func=fake_analyze,
        impact_func=fake_impact,
        compose_func=fake_compose,
    )

    assert len(run.intelligence_items) == 1
    assert run.llm_stage_count == 4
    item = run.intelligence_items[0]
    assert item.candidate.term == (
        "多主体绿电直连"
    )
    assert (
        item.feedback_ranking
        .ranking
        .recommended_answer_id
    )
    assert item.governance_batch.tasks
    assert "企业大脑" in (
        item.integrated_report_markdown
    )

    save_policy_intelligence_run(
        task=build_task(),
        run=run,
        output_dir=tmp_path,
    )

    assert (
        tmp_path / "intelligence_run.json"
    ).is_file()
    assert (
        tmp_path / "intelligence_brief.md"
    ).is_file()
    assert (
        tmp_path / "intelligence_brief.json"
    ).is_file()
    assert list(
        (
            tmp_path / "intelligence"
        ).glob("*/integrated_report.md")
    )


def test_answer_ids_are_stable() -> None:
    """模型临时 ID 应被稳定 ID 替代。"""
    package = fake_compose(
        question="问题",
        analysis=fake_analyze(
            candidate=build_candidate()
        ),
    )
    first = stabilize_answer_package_ids(
        package
    )
    second = stabilize_answer_package_ids(
        package
    )

    assert [
        candidate.answer_id
        for candidate in first.candidates
    ] == [
        candidate.answer_id
        for candidate in second.candidates
    ]
    assert all(
        candidate.answer_id.startswith(
            "answer-"
        )
        for candidate in first.candidates
    )


def test_timeliness_score_declines_with_age() -> None:
    """较新的政策应获得更高时效性得分。"""
    recent = calculate_timeliness_score(
        published_date=date(2026, 8, 5),
        reference_date=date(2026, 8, 7),
    )
    old = calculate_timeliness_score(
        published_date=date(2024, 8, 7),
        reference_date=date(2026, 8, 7),
    )

    assert recent == 100
    assert old == 45
