"""API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.models import (
    ClusterOverview,
    EmbeddingScoreBreakdown,
    GalgameChoice,
    GalgameAssetReference,
    GalgameScene,
    GalgameStoryTemplate,
    GalgameTextInference,
    InviteCode,
    ItemInstance,
    ItemTemplate,
    ItemTemplateCreate,
    RewriteRetrievalContext,
    RewritePreviewBundle,
    SessionHistoryEntry,
    SessionReport,
    SessionState,
    SessionSummary,
    UserEvolutionEntry,
    UserProfile,
    UserRecommendation,
    UserRelationship,
    VectorReindexSummary,
    VectorSearchHit,
    VectorSyncFailure,
    WorkbenchCheckpoint,
    WorkbenchEvidence,
)


class StartSessionRequest(BaseModel):
    mode: str = "core"


class RedeemInviteRequest(BaseModel):
    invite_code: str


class UserProfileResponse(BaseModel):
    user_id: str
    handle: str
    invite_code: str
    invited_by_user_id: str | None = None
    relationship_opt_in: bool = False
    recommendation_opt_in: bool = False
    created_at: str
    updated_at: str

    @classmethod
    def from_profile(cls, profile: UserProfile) -> "UserProfileResponse":
        return cls(
            user_id=profile.user_id,
            handle=profile.handle,
            invite_code=profile.invite_code,
            invited_by_user_id=profile.invited_by_user_id,
            relationship_opt_in=profile.relationship_opt_in,
            recommendation_opt_in=profile.recommendation_opt_in,
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat(),
        )


class UserAccessResponse(BaseModel):
    user_id: str
    user_secret: str
    handle: str
    relationship_opt_in: bool = False
    recommendation_opt_in: bool = False


class UserProfileUpdateRequest(BaseModel):
    relationship_opt_in: bool | None = None
    recommendation_opt_in: bool | None = None


class UserSessionListResponse(BaseModel):
    user: UserProfileResponse
    sessions: list[SessionHistoryEntry]


class UserEvolutionResponse(BaseModel):
    user: UserProfileResponse
    items: list[UserEvolutionEntry] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    id: str
    template_id: str | None = None
    prompt: str
    question_type: str
    layer: str
    scenario_tags: list[str]
    options: list[dict[str, str | float]]
    generation_mode: str = "template"
    validator_passed: bool = True
    archived: bool = False
    quality_score: float | None = None
    similarity_penalty: float | None = None

    @classmethod
    def from_item(cls, item: ItemTemplate | ItemInstance) -> "QuestionResponse":
        return cls(
            id=item.id,
            template_id=getattr(item, "template_id", None),
            prompt=item.prompt,
            question_type=item.question_type,
            layer=item.layer,
            scenario_tags=item.scenario_tags,
            options=[option.model_dump() for option in item.options],
            generation_mode=getattr(item, "generation_mode", "template"),
            validator_passed=getattr(item, "validator_passed", True),
            archived=getattr(item, "archived", False),
            quality_score=getattr(item, "quality_score", None),
            similarity_penalty=getattr(item, "similarity_penalty", None),
        )


class StartSessionResponse(BaseModel):
    session_id: str
    session_secret: str
    delete_token: str
    state: SessionState
    question: QuestionResponse
    min_questions_for_report: int = settings.min_questions_for_report
    max_questions_per_session: int = settings.max_questions_per_session
    workbench_checkpoint: WorkbenchCheckpoint | None = None


class NextQuestionRequest(BaseModel):
    session_id: str


class SubmitResponseRequest(BaseModel):
    session_id: str
    item_id: str
    option_key: str
    latency_ms: int | None = None


class SubmitResponseResponse(BaseModel):
    session_id: str
    state: SessionState
    can_generate_report: bool
    remaining_until_report: int
    next_question: QuestionResponse | None = None
    workbench_checkpoint: WorkbenchCheckpoint | None = None


class GalgameChoiceResponse(GalgameChoice):
    pass


class GalgameSceneResponse(GalgameScene):
    pass


class GalgameSceneResultResponse(BaseModel):
    session_id: str
    state: SessionState
    can_generate_report: bool
    remaining_until_report: int
    scene: GalgameScene | None = None
    text_inference: GalgameTextInference | None = None
    workbench_checkpoint: WorkbenchCheckpoint | None = None


class GalgameRespondRequest(BaseModel):
    item_id: str
    scene_id: str
    option_key: str
    choice_text: str | None = None
    custom_text: str | None = None
    latency_ms: int | None = None


class GalgameStoryTemplateRequest(BaseModel):
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


class GalgameStoryTemplateResponse(GalgameStoryTemplate):
    pass


class GalgameStoryTemplateListResponse(BaseModel):
    items: list[GalgameStoryTemplateResponse] = Field(default_factory=list)


class GalgameAssetStatusResponse(BaseModel):
    generation_enabled: bool
    backend: str
    base_url: str
    model: str = ""
    public_url_prefix: str
    background_count: int = 0
    character_count: int = 0
    sdwebui_available: bool = False
    comfyui_available: bool = False


class GalgameAssetGenerateRequest(BaseModel):
    kind: str = "background"
    key: str
    prompt: str
    force: bool = False


class GalgameStoryTemplateAssetGenerateRequest(BaseModel):
    include_character: bool = False
    force: bool = False


class GalgameAssetGenerateResponse(BaseModel):
    assets: dict[str, GalgameAssetReference] = Field(default_factory=dict)


class MapPoint(BaseModel):
    x: float
    y: float
    dimensions: dict[str, float]
    label: str | None = None
    kind: str | None = None
    cluster_name: str | None = None


class ClusterRegion(BaseModel):
    cluster_index: int
    cluster_name: str
    x: float
    y: float
    rx: float
    ry: float
    angle: float = 0.0


class MapResponse(BaseModel):
    session_id: str
    point: MapPoint
    confidence: float
    answer_points: list[MapPoint] = Field(default_factory=list)
    trajectory_points: list[MapPoint] = Field(default_factory=list)
    cluster_centers: list[MapPoint] = Field(default_factory=list)
    cluster_regions: list[ClusterRegion] = Field(default_factory=list)


class AIProviderConfigRequest(BaseModel):
    provider: str = Field(default="deepseek")
    model: str
    base_url: str
    api_key: str


class ReportGenerateRequest(BaseModel):
    naming_style: str | None = None


class AIProviderConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str
    configured: bool
    tested: bool
    message: str


class RewriteQuestionRequest(BaseModel):
    session_id: str
    item_id: str
    style_hint: str | None = None


class RewriteQuestionResponse(BaseModel):
    enabled: bool
    message: str
    preview: RewritePreviewBundle | None = None


class ItemTemplateCreateRequest(ItemTemplateCreate):
    pass


class ItemTemplateCreateResponse(BaseModel):
    item: QuestionResponse


class ClusterLabelOverrideRequest(BaseModel):
    version: str
    cluster_index: int
    name: str
    narrative_label: str


class AIConfigStatusResponse(BaseModel):
    configured: bool
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None


class VectorReindexRequest(BaseModel):
    scope: str = "all"


class VectorReindexResponse(VectorReindexSummary):
    pass


class VectorSearchResponse(BaseModel):
    enabled: bool = False
    hits: list[VectorSearchHit] = Field(default_factory=list)


class VectorSyncFailureResponse(BaseModel):
    items: list[VectorSyncFailure] = Field(default_factory=list)


class RewriteRetrievalContextResponse(RewriteRetrievalContext):
    pass


class EmbeddingScoreBreakdownResponse(EmbeddingScoreBreakdown):
    pass


class SessionSummaryResponse(SessionSummary):
    current_question: QuestionResponse | None = None
    workbench_checkpoint: WorkbenchCheckpoint | None = None


class WorkbenchEvidenceResponse(WorkbenchEvidence):
    pass


class SessionHistoryListResponse(BaseModel):
    sessions: list[SessionHistoryEntry]


class SessionAccessIssueResponse(BaseModel):
    session_id: str
    session_secret: str
    delete_token: str


class InviteCreateRequest(BaseModel):
    created_by_user_id: str | None = None
    label: str = ""
    max_uses: int = 1


class InviteResponse(BaseModel):
    code: str
    created_by_user_id: str | None = None
    label: str
    max_uses: int
    use_count: int
    active: bool
    created_at: str
    expires_at: str | None = None

    @classmethod
    def from_invite(cls, invite: InviteCode) -> "InviteResponse":
        return cls(
            code=invite.code,
            created_by_user_id=invite.created_by_user_id,
            label=invite.label,
            max_uses=invite.max_uses,
            use_count=invite.use_count,
            active=invite.active,
            created_at=invite.created_at.isoformat(),
            expires_at=invite.expires_at.isoformat() if invite.expires_at else None,
        )


class InviteListResponse(BaseModel):
    items: list[InviteResponse]


class UserListResponse(BaseModel):
    items: list[UserProfileResponse]


class RelationshipListResponse(BaseModel):
    items: list[UserRelationship]


class UserRecommendationResponse(BaseModel):
    enabled: bool
    items: list[UserRecommendation]


class TemplateListResponse(BaseModel):
    items: list[QuestionResponse]


class ItemInstanceListResponse(BaseModel):
    items: list[QuestionResponse]


class ClusterOverviewResponse(ClusterOverview):
    pass


ReportResponse = SessionReport
