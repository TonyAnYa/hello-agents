"""EnterpriseConceptRadar 核心数据模型。"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
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