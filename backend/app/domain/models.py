"""Domain models for the backend MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


QuestionLayer = Literal["core", "sub", "module", "probe", "entertainment"]
QuestionType = Literal["likert_5", "contrast_5", "binary", "triple_choice", "situational_choice"]


class QuestionOption(BaseModel):
    key: str
    text: str
    score: float


class ItemTemplate(BaseModel):
    id: str
    prompt: str
    question_type: QuestionType
    layer: QuestionLayer = "core"
    dimension_weights: dict[str, float]
    subdimension_weights: dict[str, float] = Field(default_factory=dict)
    module_affinities: dict[str, float] = Field(default_factory=dict)
    discrimination: float = 1.0
    difficulty: float = 0.0
    scenario_tags: list[str] = Field(default_factory=list)
    is_anchor: bool = False
    allow_rewrite: bool = False
    archived: bool = False
    archived_at: datetime | None = None
    options: list[QuestionOption]


class ItemInstance(BaseModel):
    id: str
    template_id: str
    session_id: str
    prompt: str
    question_type: QuestionType
    layer: QuestionLayer = "core"
    dimension_weights: dict[str, float]
    subdimension_weights: dict[str, float] = Field(default_factory=dict)
    module_affinities: dict[str, float] = Field(default_factory=dict)
    discrimination: float = 1.0
    difficulty: float = 0.0
    scenario_tags: list[str] = Field(default_factory=list)
    is_anchor: bool = False
    allow_rewrite: bool = False
    options: list[QuestionOption]
    generation_mode: Literal["template", "llm_rewrite", "anchor", "probe"] = "template"
    validator_passed: bool = True
    quality_score: float = 0.0
    similarity_penalty: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AnswerRecord(BaseModel):
    item_id: str
    template_id: str
    option_key: str
    mapped_score: float
    predicted_score: float
    residual: float
    latency_ms: int | None = None


class SessionState(BaseModel):
    core_mu: dict[str, float]
    core_sigma: dict[str, float]
    sub_mu: dict[str, float] = Field(default_factory=dict)
    sub_sigma: dict[str, float] = Field(default_factory=dict)
    sub_counts: dict[str, int] = Field(default_factory=dict)
    module_scores: dict[str, float] = Field(default_factory=dict)
    module_counts: dict[str, int] = Field(default_factory=dict)
    zeta: dict[str, float] = Field(
        default_factory=lambda: {
            "consistency": 0.5,
            "performative": 0.0,
            "exploration": 0.5,
            "fatigue": 0.0,
        }
    )
    recent_item_ids: list[str] = Field(default_factory=list)
    dimension_counts: dict[str, int] = Field(default_factory=dict)
    unlocked_subdimensions: list[str] = Field(default_factory=list)
    active_modules: list[str] = Field(default_factory=list)
    answers: list[AnswerRecord] = Field(default_factory=list)
    question_count: int = 0


class SessionRecord(BaseModel):
    session_id: str
    mode: str = "core"
    status: Literal["active", "discarded"] = "active"
    state: SessionState
    session_secret_hash: str = ""
    delete_token_hash: str = ""
    owner_key: str | None = None
    current_item_id: str | None = None
    current_template_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StructuralLabel(BaseModel):
    dimension: str
    label: str
    score: float


class ClusterMembership(BaseModel):
    cluster_index: int
    cluster_name: str
    narrative_label: str
    weight: float
    distance: float


class SubdimensionInsight(BaseModel):
    key: str
    label: str
    parent_dimension: str
    parent_label: str
    score: float
    percent: float
    sigma: float
    sample_count: int
    confidence_percent: float
    confidence_label: str
    direction_label: str
    strength_label: str
    evaluation: str
    metaphor: str


class ModuleInsight(BaseModel):
    key: str
    label: str
    score: float
    percent: float
    sample_count: int
    confidence_percent: float
    confidence_label: str
    strength_label: str
    evaluation: str
    metaphor: str


class SessionReport(BaseModel):
    session_id: str
    question_count: int
    can_exit_with_report: bool
    structural_labels: list[StructuralLabel]
    narrative_label: str
    ai_aliases: list[str] = Field(default_factory=list)
    ai_summary: str
    uncertainty_summary: dict[str, float]
    module_bars: dict[str, float]
    core_bars: dict[str, float]
    sub_bars: dict[str, float]
    cluster_name: str
    cluster_confidence: float
    cluster_mix: list[ClusterMembership] = Field(default_factory=list)
    salient_subdimensions: list[str]
    active_module_labels: list[str]
    sub_insights: list[SubdimensionInsight]
    module_insights: list[ModuleInsight]
    current_state: SessionState


class ItemTemplateCreate(BaseModel):
    prompt: str
    question_type: QuestionType = "likert_5"
    layer: QuestionLayer = "core"
    dimension_weights: dict[str, float]
    subdimension_weights: dict[str, float] = Field(default_factory=dict)
    module_affinities: dict[str, float] = Field(default_factory=dict)
    discrimination: float = 1.25
    difficulty: float = 0.0
    scenario_tags: list[str] = Field(default_factory=list)
    is_anchor: bool = False
    allow_rewrite: bool = False
    options: list[QuestionOption]


class SessionSummary(BaseModel):
    session_id: str
    question_count: int
    min_questions_for_report: int
    max_questions_per_session: int
    can_generate_report: bool
    remaining_until_report: int
    current_item_id: str | None = None
    current_template_id: str | None = None
    state: SessionState


class SessionAccessGrant(BaseModel):
    session_id: str
    session_secret: str
    delete_token: str


class TemplateRewritePreview(BaseModel):
    template_id: str
    rewritten_prompt: str
    generation_mode: Literal["template", "llm_rewrite", "anchor", "probe"]
    validator_passed: bool
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class RewriteCandidate(BaseModel):
    template_id: str
    rewritten_prompt: str
    generation_mode: Literal["template", "llm_rewrite", "anchor", "probe"]
    validator_passed: bool
    score: float
    reasons: list[str] = Field(default_factory=list)


class RewritePreviewBundle(BaseModel):
    template_id: str
    selected: TemplateRewritePreview
    candidates: list[RewriteCandidate]


class SessionHistoryEntry(BaseModel):
    session_id: str
    status: str
    question_count: int
    can_generate_report: bool
    created_at: datetime
    updated_at: datetime
    cluster_name: str | None = None
    narrative_label: str | None = None


class ClusterLabelOverride(BaseModel):
    version: str
    cluster_index: int
    name: str
    narrative_label: str
    updated_at: datetime


class ClusterDescriptor(BaseModel):
    name: str
    narrative_label: str


class ClusterVersionInfo(BaseModel):
    version: str
    sample_size: int
    cluster_count: int
    labels: list[str]
    dataset_signature: str
    created_at: datetime


class ClusterOverview(BaseModel):
    current_version: str
    sample_size: int
    cluster_count: int
    labels: list[str]
    training_history: list[ClusterVersionInfo]
    scatter_points: list[dict[str, float | str | int]] = Field(default_factory=list)
    label_overrides: list[ClusterLabelOverride] = Field(default_factory=list)
