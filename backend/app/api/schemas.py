"""API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.models import (
    ClusterOverview,
    ContextAnalysisMessage,
    ContextAnalysisRecord,
    ContextAnalysisResponse,
    EmbeddingScoreBreakdown,
    GalgameChoice,
    GalgameAssetReference,
    GalgameCharacterProfile,
    GalgameScene,
    GalgameStoryTemplate,
    GalgameTextInference,
    InviteCode,
    ItemInstance,
    ItemTemplate,
    ItemTemplateCreate,
    RewriteRetrievalContext,
    RewritePreviewBundle,
    SenrenCompanionEvent,
    SenrenCompanionSessionRecord,
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
from app.services.storage import local_session_store


class StartSessionRequest(BaseModel):
    mode: str = "core"
    story_character_mode: str | None = None
    story_character_slug: str | None = None


class GalgameCharacterProfileResponse(GalgameCharacterProfile):
    pass


class GalgameCharacterProfileListResponse(BaseModel):
    items: list[GalgameCharacterProfileResponse] = Field(default_factory=list)
    default_mode: str = "random_skill"


class RedeemInviteRequest(BaseModel):
    invite_code: str
    email: str


class LoginRequest(BaseModel):
    email: str


class LoginChallengeResponse(BaseModel):
    challenge_id: str
    expires_at: str
    delivery: str = "email"
    message: str
    dev_code: str | None = None


class LoginVerifyRequest(BaseModel):
    email: str
    challenge_id: str
    code: str


class ClaimInviteRequest(BaseModel):
    invite_code: str


class GenerateUserInviteRequest(BaseModel):
    label: str | None = None


class UserProfileResponse(BaseModel):
    user_id: str
    handle: str
    invite_code: str | None = None
    invite_available: bool = False
    invite_remaining_uses: int = 0
    invited_by_user_id: str | None = None
    email_registered: bool = False
    relationship_opt_in: bool = False
    recommendation_opt_in: bool = False
    created_at: str
    updated_at: str

    @classmethod
    def from_profile(cls, profile: UserProfile) -> "UserProfileResponse":
        invite = local_session_store.load_invite_code(profile.invite_code)
        invite_available = bool(
            invite
            and invite.created_by_user_id == profile.user_id
            and invite.active
            and invite.use_count < invite.max_uses
        )
        remaining_uses = max(0, (invite.max_uses - invite.use_count) if invite_available and invite else 0)
        return cls(
            user_id=profile.user_id,
            handle=profile.handle,
            invite_code=profile.invite_code if invite_available else None,
            invite_available=invite_available,
            invite_remaining_uses=remaining_uses,
            invited_by_user_id=profile.invited_by_user_id,
            email_registered=bool(profile.email_hash),
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


class ContextAnalysisRequest(BaseModel):
    application_id: str = Field(min_length=1, max_length=120)
    external_user_id: str = Field(min_length=1, max_length=180)
    conversation_id: str = Field(min_length=1, max_length=180)
    messages: list[ContextAnalysisMessage] = Field(min_length=1)
    consent_basis: str = Field(min_length=3, max_length=500)
    channel: str = "chat"
    locale: str = "zh-CN"
    metadata: dict[str, object] = Field(default_factory=dict)
    persist: bool = True
    persist_messages: bool = False
    include_debug: bool = False


class ContextAnalysisHistoryResponse(BaseModel):
    items: list[ContextAnalysisRecord] = Field(default_factory=list)


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
    response_format: str = ""
    quality: str = ""
    watermark: bool = False
    size_background: str = ""
    size_character: str = ""
    sequential_image_generation: str = ""
    stream: bool = False
    public_url_prefix: str
    background_count: int = 0
    character_count: int = 0
    cache_total_count: int = 0
    cache_total_bytes: int = 0
    cache_max_files: int = 0
    cache_max_age_days: int = 0
    cleanup_enabled: bool = False
    sdwebui_available: bool = False
    comfyui_available: bool = False
    cloud_configured: bool = False
    diagnostics: list[str] = Field(default_factory=list)


class GalgameAssetGenerateRequest(BaseModel):
    kind: str = "background"
    key: str
    prompt: str
    force: bool = False


class GalgameStoryTemplateAssetGenerateRequest(BaseModel):
    include_character: bool = False
    force: bool = False


class SenrenCharacterAssetGenerateRequest(BaseModel):
    force: bool = False


class SenrenCompanionStartRequest(BaseModel):
    client_id: str = Field(default="", max_length=160)
    game_title: str = Field(default="Senren Banka", max_length=120)
    game_path: str = Field(default="", max_length=500)
    game_path_fingerprint: str = Field(default="", max_length=160)
    game_info: dict[str, object] = Field(default_factory=dict)


class SenrenCompanionChoiceRequest(BaseModel):
    choice_id: str = Field(min_length=1, max_length=120)
    option_key: str = Field(min_length=1, max_length=120)
    choice_text: str = Field(default="", max_length=2000)
    dialogue_text: str = Field(default="", max_length=6000)
    scene_title: str = Field(default="", max_length=500)


class SenrenCompanionEventRequest(BaseModel):
    event_type: str = Field(default="scene_text", max_length=80)
    scene_title: str = Field(default="", max_length=500)
    dialogue_text: str = Field(default="", max_length=6000)
    visible_choices: list[str] = Field(default_factory=list, max_length=12)
    route_marker: str = Field(default="", max_length=500)
    source: str = Field(default="manual", max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


class SenrenCompanionStartResponse(BaseModel):
    session_id: str
    session_secret: str
    delete_token: str
    record: SenrenCompanionSessionRecord
    roadmap: dict[str, object] = Field(default_factory=dict)
    total_choices: int = 0


class SenrenCompanionChoiceResponse(BaseModel):
    record: SenrenCompanionSessionRecord
    state: dict[str, object] = Field(default_factory=dict)
    choice_recorded: dict[str, object] = Field(default_factory=dict)
    total_choices_made: int = 0
    current_route: str | None = None
    can_generate_report: bool = False
    remaining_until_report: int = 0


class SenrenCompanionEventResponse(BaseModel):
    record: SenrenCompanionSessionRecord
    event: SenrenCompanionEvent
    stored_events_count: int = 0


class SenrenCompanionSessionListResponse(BaseModel):
    items: list[SenrenCompanionSessionRecord] = Field(default_factory=list)


class SenrenCompanionReportResponse(BaseModel):
    record: SenrenCompanionSessionRecord
    report: dict[str, object]


class GalgameAssetGenerateResponse(BaseModel):
    assets: dict[str, GalgameAssetReference] = Field(default_factory=dict)


class GalgameAssetCleanupRequest(BaseModel):
    max_files: int | None = None
    max_age_days: int | None = None


class GalgameAssetCleanupResponse(BaseModel):
    deleted_count: int = 0
    remaining_count: int = 0
    remaining_bytes: int = 0


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
