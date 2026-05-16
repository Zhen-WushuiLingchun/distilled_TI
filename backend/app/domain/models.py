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


class GalgameTurn(BaseModel):
    turn_id: str
    session_id: str
    item_id: str
    template_id: str
    scene_id: str
    selected_option_key: str
    custom_text: str | None = None
    scene_text: str = ""
    inferred_option_key: str | None = None
    inference_confidence: float | None = None
    inference_reason: str | None = None
    classifier_source: Literal["none", "rule", "embedding", "pairwise", "llm", "hybrid"] = "none"
    inference_distribution: dict[str, float] = Field(default_factory=dict)
    embedding_similarity: dict[str, float] = Field(default_factory=dict)
    pairwise_scores: dict[str, float] = Field(default_factory=dict)
    story_template_id: str | None = None
    ai_generated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
    user_id: str | None = None
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


class SupportRiskFlag(BaseModel):
    key: str
    severity: Literal["low", "medium", "high"]
    label: str
    evidence: list[str] = Field(default_factory=list)
    suggested_action: str
    diagnostic: bool = False


class ContextAnalysisMessage(BaseModel):
    role: Literal["user", "assistant", "system", "tool"] = "user"
    content: str
    timestamp: datetime | None = None


class ContextAnalysisSignal(BaseModel):
    key: str
    label: str
    severity: Literal["low", "medium", "high", "crisis"]
    confidence: float
    source: Literal["rule", "embedding", "llm", "hybrid"]
    evidence: list[str] = Field(default_factory=list)
    suggested_action: str
    diagnostic: bool = False


class ContextAnalysisResponse(BaseModel):
    analysis_id: str
    application_id: str
    external_user_id: str
    conversation_id: str
    risk_level: Literal["none", "low", "medium", "high", "crisis"]
    risk_score: float
    cluster: str
    confidence: float
    signals: list[ContextAnalysisSignal] = Field(default_factory=list)
    immediate_actions: list[str] = Field(default_factory=list)
    escalation_required: bool = False
    human_review_recommended: bool = False
    evidence_window: list[str] = Field(default_factory=list)
    model_usage: dict[str, object] = Field(default_factory=dict)
    method_version: str = "context_support_signals_v1"
    diagnostic: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ContextAnalysisRecord(BaseModel):
    analysis_id: str
    application_id: str
    external_user_id: str
    conversation_id: str
    risk_level: Literal["none", "low", "medium", "high", "crisis"]
    request_payload: dict[str, object] = Field(default_factory=dict)
    response: ContextAnalysisResponse
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
    support_risk_flags: list[SupportRiskFlag] = Field(default_factory=list)
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


class WorkbenchSignal(BaseModel):
    key: str
    label: str
    value: float
    confidence_percent: float = 0.0
    sample_count: int = 0
    detail: str | None = None


class WorkbenchMilestone(BaseModel):
    milestone: int
    status: Literal["completed", "current", "upcoming"]
    question_delta: int
    progress_percent: float
    snapshot_expected: bool = False


class WorkbenchCheckpoint(BaseModel):
    question_count: int
    report_ready: bool
    report_target: int
    remaining_until_report: int
    report_progress_percent: float
    previous_milestone: int | None = None
    next_milestone: int | None = None
    milestone_progress_percent: float
    snapshot_due_now: bool = False
    narrative: str
    top_core_signals: list[WorkbenchSignal] = Field(default_factory=list)
    uncertainty_queue: list[WorkbenchSignal] = Field(default_factory=list)
    active_modules: list[WorkbenchSignal] = Field(default_factory=list)
    unlocked_subdimensions: list[WorkbenchSignal] = Field(default_factory=list)
    milestones: list[WorkbenchMilestone] = Field(default_factory=list)


class WorkbenchEvidenceItem(BaseModel):
    reference_key: str
    object_type: Literal["template", "rewrite_candidate", "item_instance", "session_snapshot", "galgame_turn"]
    label: str
    relationship: str
    prompt_excerpt: str
    confidence_tier: Literal["high", "medium", "low"]
    scenario_tags: list[str] = Field(default_factory=list)
    snapshot_milestone: int | None = None


class WorkbenchEvidence(BaseModel):
    enabled: bool = False
    current_question_id: str | None = None
    current_template_id: str | None = None
    vector_available: bool = False
    reranker_applied: bool = False
    item_evidence: list[WorkbenchEvidenceItem] = Field(default_factory=list)
    session_evidence: list[WorkbenchEvidenceItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class GalgameChoice(BaseModel):
    key: str
    text: str
    option_key: str
    score: float
    tone: str


class GalgameAssetReference(BaseModel):
    kind: Literal["background", "character", "audio"]
    key: str
    prompt: str = ""
    url: str | None = None
    source: Literal["generated", "fallback", "external", "none"] = "fallback"
    status: Literal["ready", "disabled", "failed", "missing"] = "ready"


class GalgameScene(BaseModel):
    scene_id: str
    session_id: str
    item_id: str
    template_id: str
    title: str
    location: str
    mood: str
    speaker: str
    narrator_text: str
    character_text: str
    prompt_shadow: str
    choices: list[GalgameChoice]
    memory_fragments: list[str] = Field(default_factory=list)
    background_key: str = "campus_window"
    background_prompt: str = ""
    character_key: str = "desk_mate"
    character_prompt: str = ""
    background_asset: GalgameAssetReference | None = None
    character_asset: GalgameAssetReference | None = None
    audio_asset: GalgameAssetReference | None = None
    story_template_id: str | None = None
    ai_generated: bool = False
    custom_input_enabled: bool = True


class GalgameOptionTendency(BaseModel):
    option_key: str
    llm_score: float | None = None
    embedding_score: float | None = None
    pairwise_score: float | None = None
    fused_score: float = 0.0
    reason: str = ""


class GalgameTextInference(BaseModel):
    inferred_option_key: str | None = None
    confidence: float = 0.0
    reason: str = ""
    source: Literal["none", "rule", "embedding", "pairwise", "llm", "hybrid"] = "none"
    option_scores: list[GalgameOptionTendency] = Field(default_factory=list)
    embedding_available: bool = False
    pairwise_available: bool = False
    llm_available: bool = False
    method_version: str = "free_text_pairwise_fusion_v2"


class GalgameStoryTemplate(BaseModel):
    template_id: str
    owner_user_id: str | None = None
    name: str
    description: str = ""
    location: str
    speaker: str
    character_key: str = "desk_mate"
    background_key: str = "campus_window"
    background_prompt: str = ""
    character_prompt: str = ""
    style_prompt: str = ""
    scenario_tags: list[str] = Field(default_factory=list)
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionAccessGrant(BaseModel):
    session_id: str
    session_secret: str
    delete_token: str


class UserProfile(BaseModel):
    user_id: str
    handle: str
    invite_code: str
    invited_by_user_id: str | None = None
    email_hash: str | None = None
    user_secret_hash: str = ""
    relationship_opt_in: bool = False
    recommendation_opt_in: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserAccessGrant(BaseModel):
    user_id: str
    user_secret: str
    handle: str
    relationship_opt_in: bool = False
    recommendation_opt_in: bool = False


class InviteCode(BaseModel):
    code: str
    created_by_user_id: str | None = None
    label: str = ""
    max_uses: int = 1
    use_count: int = 0
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None


class UserRelationship(BaseModel):
    relationship_id: str
    source_user_id: str
    target_user_id: str
    relationship_type: Literal["invited"] = "invited"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserRecommendation(BaseModel):
    subject_user_id: str
    candidate_user_id: str
    candidate_handle: str
    score: float
    reason: str
    shared_cluster_name: str | None = None
    via_relationship: str | None = None


class EmbeddingScoreBreakdown(BaseModel):
    enabled: bool = False
    source_similarity: float = 0.0
    source_distance_score: float = 0.0
    duplicate_similarity: float = 0.0
    duplicate_penalty: float = 0.0
    alignment_similarity: float = 0.0
    alignment_bonus: float = 0.0
    total: float = 0.0


class VectorSearchHit(BaseModel):
    object_id: str
    object_type: Literal["template", "rewrite_candidate", "item_instance", "session_snapshot", "galgame_turn"]
    template_id: str | None = None
    instance_id: str | None = None
    session_id: str | None = None
    snapshot_milestone: int | None = None
    layer: str
    generation_mode: str
    prompt_excerpt: str
    score: float
    rerank_score: float | None = None
    scenario_tags: list[str] = Field(default_factory=list)


class RewriteRetrievalContext(BaseModel):
    enabled: bool = False
    reranker_applied: bool = False
    template_hits: list[VectorSearchHit] = Field(default_factory=list)
    item_instance_hits: list[VectorSearchHit] = Field(default_factory=list)
    rewrite_candidate_hits: list[VectorSearchHit] = Field(default_factory=list)


class TemplateRewritePreview(BaseModel):
    template_id: str
    rewritten_prompt: str
    generation_mode: Literal["template", "llm_rewrite", "anchor", "probe"]
    validator_passed: bool
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    embedding_score_breakdown: EmbeddingScoreBreakdown | None = None


class RewriteCandidate(BaseModel):
    template_id: str
    rewritten_prompt: str
    generation_mode: Literal["template", "llm_rewrite", "anchor", "probe"]
    validator_passed: bool
    score: float
    reasons: list[str] = Field(default_factory=list)
    embedding_score_breakdown: EmbeddingScoreBreakdown | None = None


class RewritePreviewBundle(BaseModel):
    template_id: str
    selected: TemplateRewritePreview
    candidates: list[RewriteCandidate]
    retrieval_context: RewriteRetrievalContext | None = None


class VectorSyncFailure(BaseModel):
    failure_id: str
    object_type: str
    object_id: str
    operation: str
    error_message: str
    payload_json: str
    created_at: datetime


class VectorReindexSummary(BaseModel):
    scope: Literal["templates", "instances", "sessions", "galgame_turns", "all"]
    enabled: bool = False
    indexed_count: int = 0
    failed_count: int = 0
    failure_ids: list[str] = Field(default_factory=list)


class SessionHistoryEntry(BaseModel):
    session_id: str
    mode: str = "core"
    user_id: str | None = None
    user_handle: str | None = None
    status: str
    question_count: int
    can_generate_report: bool
    created_at: datetime
    updated_at: datetime
    cluster_name: str | None = None
    narrative_label: str | None = None


class UserEvolutionEntry(BaseModel):
    session_id: str
    question_count: int
    can_generate_report: bool
    cluster_name: str | None = None
    narrative_label: str | None = None
    core_mu: dict[str, float] = Field(default_factory=dict)
    zeta: dict[str, float] = Field(default_factory=dict)
    active_modules: list[str] = Field(default_factory=list)
    updated_at: datetime
    core_delta_from_previous: dict[str, float] = Field(default_factory=dict)


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
