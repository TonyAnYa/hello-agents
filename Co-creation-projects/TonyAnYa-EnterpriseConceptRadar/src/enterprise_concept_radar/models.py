"""EnterpriseConceptRadar 核心数据模型。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class PolicyDocumentType(str, Enum):
    """政策文件类型。"""

    NOTICE = "通知"
    PLAN = "规划"
    ANNOUNCEMENT = "公告"
    INTERPRETATION = "政策解读"
    PRESS_CONFERENCE = "新闻发布会"
    CONSULTATION = "征求意见稿"
    STANDARD = "行业标准"
    OTHER = "其他"


class ConceptCandidateType(str, Enum):
    """候选概念的变化类型。"""

    NEW_CONCEPT = "新增概念"
    NEW_EXPRESSION = "新增说法"
    HEATING_CONCEPT = "升温概念"
    DEFINITION_CHANGE = "定义变化"
    RELATED_CONCEPT = "相近概念"

class BaselineTerm(BaseModel):
    """历史术语基线中的一个已知概念。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    term: str = Field(
        min_length=1,
        description="标准术语名称",
    )
    first_seen_date: date | None = Field(
        default=None,
        description="基线中记录的最早出现日期",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="别名或历史表述",
    )
    source: str | None = Field(
        default=None,
        description="基线记录来源",
    )


class ConceptBaseline(BaseModel):
    """用于判断概念新颖度的历史术语基线。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    baseline_name: str = Field(
        min_length=1,
        description="基线名称",
    )
    version: str = Field(
        min_length=1,
        description="基线版本",
    )
    known_terms: list[BaselineTerm] = Field(
        default_factory=list,
        description="基线内的已知术语",
    )

class PolicyDocument(BaseModel):
    """经过标准化处理的政策文档。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    document_id: str = Field(
        min_length=1,
        description="政策文档唯一标识",
    )
    title: str = Field(
        min_length=1,
        description="政策文件标题",
    )
    source_name: str = Field(
        min_length=1,
        description="发布机构名称",
    )
    source_url: AnyUrl = Field(
        description="权威来源地址",
    )
    published_date: date = Field(
        description="政策发布日期",
    )
    document_type: PolicyDocumentType = Field(
        description="政策文件类型",
    )
    content: str = Field(
        min_length=20,
        description="政策正文或经过清洗的正文",
    )

    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="系统采集时间",
    )
    is_simulated: bool = Field(
        default=False,
        description="是否为教学模拟数据",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="政策关键词",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展元数据",
    )

    @field_validator("keywords")
    @classmethod
    def normalize_keywords(
        cls,
        keywords: list[str],
    ) -> list[str]:
        """去除空关键词和重复关键词，并保持原顺序。"""
        normalized: list[str] = []

        for keyword in keywords:
            cleaned = keyword.strip()

            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)

        return normalized


class ConceptCandidate(BaseModel):
    """从政策文档中发现的候选新概念。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    term: str = Field(
        min_length=1,
        description="候选新词或新概念",
    )
    source_document_id: str = Field(
        min_length=1,
        description="概念来源政策文档 ID",
    )
    evidence_quote: str = Field(
        min_length=1,
        description="支持该概念判断的政策原文",
    )
    candidate_type: ConceptCandidateType = Field(
        description="候选概念变化类型",
    )

    novelty_score: float = Field(
        ge=0,
        le=100,
        description="新颖度评分",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="概念识别置信度",
    )

    first_seen_date: date | None = Field(
        default=None,
        description="系统已知的最早出现日期",
    )
    related_terms: list[str] = Field(
        default_factory=list,
        description="相近概念或历史表述",
    )
    explanation: str | None = Field(
        default=None,
        description="概念初步解释",
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="系统识别时间",
    )


class AnswerEvaluation(BaseModel):
    """问题与候选回答的适配度评估结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        description="管理人员提出的问题",
    )
    answer_id: str = Field(
        min_length=1,
        description="候选回答唯一标识",
    )

    semantic_relevance: float = Field(
        ge=0,
        le=100,
        description="语义相关性",
    )
    keyword_coverage: float = Field(
        ge=0,
        le=100,
        description="关键词覆盖率",
    )
    authority_score: float = Field(
        ge=0,
        le=100,
        description="权威依据充分度",
    )
    timeliness_score: float = Field(
        ge=0,
        le=100,
        description="政策时效性",
    )
    business_relevance: float = Field(
        ge=0,
        le=100,
        description="广东电网业务关联度",
    )
    actionability_score: float = Field(
        ge=0,
        le=100,
        description="管理行动建议完整度",
    )
    user_feedback_score: float = Field(
        ge=0,
        le=100,
        default=50,
        description="用户反馈折算分",
    )

    comments: list[str] = Field(
        default_factory=list,
        description="评估说明",
    )

    @computed_field
    @property
    def total_score(self) -> float:
        """按照项目指标权重计算回答适配度总分。"""
        score = (
            self.semantic_relevance * 0.25
            + self.keyword_coverage * 0.15
            + self.authority_score * 0.20
            + self.timeliness_score * 0.10
            + self.business_relevance * 0.15
            + self.actionability_score * 0.10
            + self.user_feedback_score * 0.05
        )

        return round(score, 2)
class ConceptAnalysis(BaseModel):
    """模型生成的结构化概念分析草稿。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    term: str = Field(
        min_length=1,
        description="被分析的候选概念",
    )
    source_document_id: str = Field(
        min_length=1,
        description="来源政策文档 ID",
    )
    source_is_simulated: bool = Field(
        description="来源是否为教学模拟数据",
    )

    explanation_draft: str = Field(
        min_length=1,
        description="概念解释草稿，不等同于权威定义",
    )
    source_facts: list[str] = Field(
        default_factory=list,
        description="能够直接由输入政策原文支持的事实",
    )
    rule_judgements: list[str] = Field(
        default_factory=list,
        description="由确定性规则得出的判断",
    )
    model_inferences: list[str] = Field(
        default_factory=list,
        description="模型根据材料作出的推断",
    )
    related_term_comparison: list[str] = Field(
        default_factory=list,
        description="与相近历史术语的区别和联系",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="当前材料无法确认的事项",
    )
    verification_actions: list[str] = Field(
        default_factory=list,
        description="后续权威核验建议",
    )

    confidence: float = Field(
        ge=0,
        le=1,
        description="分析草稿置信度",
    )
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="分析生成时间",
    )
class BusinessDomain(str, Enum):
    """广东电网业务影响领域。"""

    PLANNING = "规划建设"
    DISPATCH = "调度运行"
    MARKET = "市场交易"
    METERING = "计量结算"
    SAFETY = "安全责任"
    KNOWLEDGE_GOVERNANCE = "知识治理"


class ImpactLevel(str, Enum):
    """业务影响程度。"""

    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"
    UNCERTAIN = "待核验"

class BusinessDomainImpact(BaseModel):
    """一个业务领域的影响分析。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    domain: BusinessDomain = Field(
        description="广东电网业务领域",
    )
    impact_level: ImpactLevel = Field(
        description="影响程度",
    )
    impact_summary: str = Field(
        min_length=1,
        description="影响摘要",
    )
    affected_processes: list[str] = Field(
        default_factory=list,
        description="可能受影响的业务流程",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="潜在风险",
    )
    opportunities: list[str] = Field(
        default_factory=list,
        description="潜在机会",
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="建议采取的行动",
    )
    evidence_basis: list[str] = Field(
        default_factory=list,
        description="支持判断的输入事实或分析依据",
    )


class BusinessImpactAssessment(BaseModel):
    """候选政策概念对广东电网的业务影响评估草稿。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    term: str = Field(
        min_length=1,
        description="被评估的政策概念",
    )
    source_document_id: str = Field(
        min_length=1,
        description="来源政策文档 ID",
    )
    source_is_simulated: bool = Field(
        description="来源是否为教学模拟数据",
    )

    overall_summary: str = Field(
        min_length=1,
        description="总体业务影响摘要",
    )
    domain_impacts: list[BusinessDomainImpact] = Field(
        min_length=1,
        description="分领域业务影响",
    )
    cross_domain_issues: list[str] = Field(
        default_factory=list,
        description="跨专业协同事项",
    )
    governance_tasks: list[str] = Field(
        default_factory=list,
        description="建议发起的知识治理任务",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="当前无法确认的事项",
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="业务影响评估置信度",
    )
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="评估生成时间",
    )

    @field_validator("domain_impacts")
    @classmethod
    def domain_impacts_must_be_unique(
        cls,
        impacts: list[BusinessDomainImpact],
    ) -> list[BusinessDomainImpact]:
        """同一业务领域不能重复出现。"""
        domains = [
            impact.domain
            for impact in impacts
        ]

        if len(domains) != len(set(domains)):
            raise ValueError(
                "domain_impacts 中存在重复业务领域"
            )

        return impacts
class AnswerStyle(str, Enum):
    """候选回答的表达风格。"""

    EXECUTIVE_BRIEF = "管理摘要型"
    PROFESSIONAL_ANALYSIS = "专业分析型"
class AnswerCandidate(BaseModel):
    """面向管理人员的一个候选回答。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    answer_id: str = Field(
        min_length=1,
        description="候选回答唯一标识",
    )
    style: AnswerStyle = Field(
        description="回答表达风格",
    )
    title: str = Field(
        min_length=1,
        description="回答标题",
    )
    content: str = Field(
        min_length=20,
        description="回答正文",
    )
    evidence_references: list[str] = Field(
        default_factory=list,
        description="回答引用的证据说明",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="建议采取的行动",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="限制条件和不确定事项",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="候选回答生成时间",
    )


class AnswerPackage(BaseModel):
    """同一问题对应的两份候选回答。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        description="管理人员提出的问题",
    )
    term: str = Field(
        min_length=1,
        description="问题涉及的政策概念",
    )
    source_document_id: str = Field(
        min_length=1,
        description="来源政策文档 ID",
    )
    source_is_simulated: bool = Field(
        description="来源是否为教学模拟数据",
    )
    candidates: list[AnswerCandidate] = Field(
        min_length=2,
        max_length=2,
        description="两份候选回答",
    )

    @field_validator("candidates")
    @classmethod
    def candidates_must_be_distinct(
        cls,
        candidates: list[AnswerCandidate],
    ) -> list[AnswerCandidate]:
        """两份候选回答必须具有不同 ID 和表达风格。"""
        answer_ids = [
            candidate.answer_id
            for candidate in candidates
        ]
        styles = [
            candidate.style
            for candidate in candidates
        ]

        if len(set(answer_ids)) != 2:
            raise ValueError(
                "两份候选回答的 answer_id 必须不同"
            )

        if len(set(styles)) != 2:
            raise ValueError(
                "两份候选回答应使用不同表达风格"
            )

        return candidates
class AnswerRankingResult(BaseModel):
    """两份候选回答的评分与推荐结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        description="用户问题",
    )
    term: str = Field(
        min_length=1,
        description="问题涉及的政策概念",
    )
    source_document_id: str = Field(
        min_length=1,
        description="来源政策文档 ID",
    )
    source_is_simulated: bool = Field(
        description="来源是否为教学模拟数据",
    )
    required_keywords: list[str] = Field(
        default_factory=list,
        description="本轮评分使用的必要关键词",
    )
    evaluations: list[AnswerEvaluation] = Field(
        min_length=2,
        max_length=2,
        description="两份候选回答的评分结果",
    )
    recommended_answer_id: str = Field(
        min_length=1,
        description="推荐回答 ID",
    )
    recommendation_reason: str = Field(
        min_length=1,
        description="推荐理由",
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="评分时间",
    )

    @field_validator("evaluations")
    @classmethod
    def evaluation_ids_must_be_distinct(
        cls,
        evaluations: list[AnswerEvaluation],
    ) -> list[AnswerEvaluation]:
        """两份评分结果必须对应不同回答。"""
        answer_ids = [
            evaluation.answer_id
            for evaluation in evaluations
        ]

        if len(set(answer_ids)) != 2:
            raise ValueError(
                "两份评分结果的 answer_id 必须不同"
            )

        return evaluations

    @model_validator(mode="after")
    def recommended_answer_must_exist(
        self,
    ) -> "AnswerRankingResult":
        """推荐回答必须存在于评分结果中。"""
        answer_ids = {
            evaluation.answer_id
            for evaluation in self.evaluations
        }

        if self.recommended_answer_id not in answer_ids:
            raise ValueError(
                "recommended_answer_id 不在评分结果中"
            )

        return self
class FeedbackRating(str, Enum):
    """用户对回答专业质量的评价。"""

    PROFESSIONAL = "专业"
    AVERAGE = "一般"
    MISMATCH = "不匹配"


class FeedbackAction(str, Enum):
    """用户对回答采取的行为。"""

    ADOPT = "采纳"
    COPY = "复制"
class AnswerFeedbackEvent(BaseModel):
    """一次用户回答反馈事件。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    event_id: str = Field(
        default_factory=lambda: uuid4().hex,
        min_length=1,
        description="反馈事件唯一标识",
    )
    answer_id: str = Field(
        min_length=1,
        description="反馈对应的回答 ID",
    )
    question: str | None = Field(
        default=None,
        description="反馈对应的用户问题",
    )
    rating: FeedbackRating | None = Field(
        default=None,
        description="专业、一般或不匹配评价",
    )
    action: FeedbackAction | None = Field(
        default=None,
        description="采纳或复制行为",
    )
    comment: str | None = Field(
        default=None,
        max_length=500,
        description="用户补充意见",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="反馈记录时间",
    )

    @model_validator(mode="after")
    def at_least_one_feedback_signal(
        self,
    ) -> "AnswerFeedbackEvent":
        """反馈必须包含评价或行为信号。"""
        if self.rating is None and self.action is None:
            raise ValueError(
                "反馈必须至少包含 rating 或 action"
            )

        return self


class AnswerFeedbackSummary(BaseModel):
    """一个候选回答的用户反馈聚合结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    answer_id: str = Field(
        min_length=1,
        description="被聚合的回答 ID",
    )
    total_events: int = Field(
        ge=0,
        description="反馈事件总数",
    )
    rating_counts: dict[str, int] = Field(
        default_factory=dict,
        description="各评价类型的数量",
    )
    action_counts: dict[str, int] = Field(
        default_factory=dict,
        description="各行为类型的数量",
    )
    rating_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="评价信号得分",
    )
    action_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="行为信号得分",
    )
    user_feedback_score: float = Field(
        ge=0,
        le=100,
        description="最终用户反馈得分",
    )
class FeedbackAwareRankingResult(BaseModel):
    """使用历史反馈重新评分后的推荐结果。"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    ranking: AnswerRankingResult = Field(
        description="使用反馈分重新计算的排名结果",
    )
    feedback_summaries: list[AnswerFeedbackSummary] = Field(
        min_length=2,
        max_length=2,
        description="两份候选回答的反馈聚合结果",
    )

    @model_validator(mode="after")
    def feedback_answer_ids_must_match(
        self,
    ) -> "FeedbackAwareRankingResult":
        """反馈汇总必须与排名中的回答一一对应。"""
        ranking_answer_ids = {
            evaluation.answer_id
            for evaluation in self.ranking.evaluations
        }
        feedback_answer_ids = {
            summary.answer_id
            for summary in self.feedback_summaries
        }

        if len(feedback_answer_ids) != 2:
            raise ValueError(
                "两份反馈汇总的 answer_id 必须不同"
            )

        if feedback_answer_ids != ranking_answer_ids:
            raise ValueError(
                "反馈汇总与排名结果的 answer_id 不一致"
            )

        return self