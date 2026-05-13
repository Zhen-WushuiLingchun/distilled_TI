"""Local admin API routes."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import (
    AIConfigStatusResponse,
    AIProviderConfigRequest,
    AIProviderConfigResponse,
    ClusterOverviewResponse,
    ClusterLabelOverrideRequest,
    GalgameStoryTemplateListResponse,
    GalgameAssetGenerateRequest,
    GalgameAssetGenerateResponse,
    GalgameAssetStatusResponse,
    GalgameStoryTemplateAssetGenerateRequest,
    GalgameStoryTemplateRequest,
    GalgameStoryTemplateResponse,
    InviteCreateRequest,
    InviteListResponse,
    InviteResponse,
    ItemInstanceListResponse,
    ItemTemplateCreateRequest,
    ItemTemplateCreateResponse,
    QuestionResponse,
    RelationshipListResponse,
    RewriteQuestionRequest,
    RewriteQuestionResponse,
    SessionAccessIssueResponse,
    SessionHistoryListResponse,
    TemplateListResponse,
    UserListResponse,
    UserProfileResponse,
    UserRecommendationResponse,
    VectorReindexRequest,
    VectorReindexResponse,
    VectorSearchResponse,
    VectorSyncFailureResponse,
)
from app.api.security import build_owner_key, require_local_admin
from app.core.config import settings
from app.domain.models import GalgameStoryTemplate
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.galgame_asset_service import galgame_asset_service
from app.services.session_service import session_service
from app.services.storage import local_session_store
from app.services.user_service import user_service
from app.services.vector_indexer import vector_indexer

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/session/{session_id}/access", response_model=SessionAccessIssueResponse)
def issue_session_access(session_id: str, request: Request) -> SessionAccessIssueResponse:
    require_local_admin(request)
    try:
        access = session_service.issue_session_access(session_id, build_owner_key(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionAccessIssueResponse(**access.model_dump())


@router.post("/ai/config", response_model=AIProviderConfigResponse)
def configure_ai_provider(payload: AIProviderConfigRequest, request: Request) -> AIProviderConfigResponse:
    require_local_admin(request)
    config = AIProviderConfig(
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )
    tested, message = ai_service.test_config(config)
    if not tested:
        raise HTTPException(status_code=422, detail=message)
    config = ai_service.configure(
        provider=payload.provider,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )
    return AIProviderConfigResponse(
        provider=config.provider,
        model=config.model,
        base_url=config.base_url,
        configured=True,
        tested=True,
        message=message,
    )


@router.get("/ai/config", response_model=AIConfigStatusResponse)
def get_ai_provider_config(request: Request) -> AIConfigStatusResponse:
    require_local_admin(request)
    config = ai_service.get_public_config()
    if config is None:
        return AIConfigStatusResponse(configured=False)
    return AIConfigStatusResponse(**config)


@router.post("/admin/invites", response_model=InviteResponse)
def create_invite(payload: InviteCreateRequest, request: Request) -> InviteResponse:
    require_local_admin(request)
    if payload.created_by_user_id and local_session_store.load_user_profile(payload.created_by_user_id) is None:
        raise HTTPException(status_code=404, detail="created_by_user_not_found")
    invite = user_service.create_invite(
        created_by_user_id=payload.created_by_user_id,
        label=payload.label,
        max_uses=payload.max_uses,
    )
    return InviteResponse.from_invite(invite)


@router.get("/admin/invites", response_model=InviteListResponse)
def list_invites(request: Request, limit: int = 100) -> InviteListResponse:
    require_local_admin(request)
    return InviteListResponse(items=[InviteResponse.from_invite(invite) for invite in user_service.list_invites(limit)])


@router.get("/admin/users", response_model=UserListResponse)
def list_users(request: Request, limit: int = 100) -> UserListResponse:
    require_local_admin(request)
    return UserListResponse(items=[UserProfileResponse.from_profile(profile) for profile in user_service.list_users(limit)])


@router.get("/admin/users/relationships", response_model=RelationshipListResponse)
def list_user_relationships(request: Request, user_id: str | None = None, limit: int = 200) -> RelationshipListResponse:
    require_local_admin(request)
    return RelationshipListResponse(items=user_service.list_relationships(user_id=user_id, limit=limit))


@router.get("/admin/users/{user_id}/recommendations", response_model=UserRecommendationResponse)
def user_recommendations(request: Request, user_id: str, limit: int = 5) -> UserRecommendationResponse:
    require_local_admin(request)
    if local_session_store.load_user_profile(user_id) is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    return UserRecommendationResponse(
        enabled=settings.relationship_recommendations_enabled,
        items=user_service.recommend_candidates(user_id, limit),
    )


@router.post("/ai/rewrite-question", response_model=RewriteQuestionResponse)
def rewrite_question(payload: RewriteQuestionRequest, request: Request) -> RewriteQuestionResponse:
    require_local_admin(request)
    try:
        preview = session_service.preview_rewrite(
            payload.session_id,
            payload.item_id,
            payload.style_hint,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    message = f"已为模板 {payload.item_id} 生成受限改写预览。"
    return RewriteQuestionResponse(enabled=True, message=message, preview=preview)


@router.post("/admin/vector/reindex", response_model=VectorReindexResponse)
def reindex_vectors(payload: VectorReindexRequest, request: Request) -> VectorReindexResponse:
    require_local_admin(request)
    scope = str(payload.scope or "all")
    if scope not in {"templates", "instances", "sessions", "galgame_turns", "all"}:
        raise HTTPException(status_code=422, detail="invalid_vector_scope")
    summary = vector_indexer.reindex(scope)  # type: ignore[arg-type]
    return VectorReindexResponse(**summary.model_dump())


@router.get("/admin/galgame/story-templates", response_model=GalgameStoryTemplateListResponse)
def list_galgame_story_templates(
    request: Request,
    include_inactive: bool = True,
) -> GalgameStoryTemplateListResponse:
    require_local_admin(request)
    return GalgameStoryTemplateListResponse(
        items=[
            GalgameStoryTemplateResponse(**template.model_dump())
            for template in session_service.list_galgame_story_templates(include_inactive=include_inactive)
        ]
    )


@router.post("/admin/galgame/story-templates", response_model=GalgameStoryTemplateResponse)
def create_galgame_story_template(
    payload: GalgameStoryTemplateRequest,
    request: Request,
) -> GalgameStoryTemplateResponse:
    require_local_admin(request)
    template = session_service.save_galgame_story_template(
        GalgameStoryTemplate(
            template_id=f"story-{uuid4().hex[:12]}",
            **payload.model_dump(),
        )
    )
    return GalgameStoryTemplateResponse(**template.model_dump())


@router.put("/admin/galgame/story-templates/{template_id}", response_model=GalgameStoryTemplateResponse)
def update_galgame_story_template(
    template_id: str,
    payload: GalgameStoryTemplateRequest,
    request: Request,
) -> GalgameStoryTemplateResponse:
    require_local_admin(request)
    template = session_service.save_galgame_story_template(
        GalgameStoryTemplate(
            template_id=template_id,
            **payload.model_dump(),
        )
    )
    return GalgameStoryTemplateResponse(**template.model_dump())


@router.delete("/admin/galgame/story-templates/{template_id}")
def delete_galgame_story_template(template_id: str, request: Request) -> dict[str, bool]:
    require_local_admin(request)
    try:
        session_service.delete_galgame_story_template(template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}


@router.get("/admin/galgame/assets/status", response_model=GalgameAssetStatusResponse)
def galgame_asset_status(request: Request) -> GalgameAssetStatusResponse:
    require_local_admin(request)
    return GalgameAssetStatusResponse(**galgame_asset_service.status())


@router.post("/admin/galgame/assets/generate", response_model=GalgameAssetGenerateResponse)
def generate_galgame_asset(payload: GalgameAssetGenerateRequest, request: Request) -> GalgameAssetGenerateResponse:
    require_local_admin(request)
    try:
        asset = galgame_asset_service.generate_image_asset(
            kind=payload.kind,
            key=payload.key,
            prompt=payload.prompt,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"galgame_asset_generation_failed: {exc}") from exc
    return GalgameAssetGenerateResponse(assets={asset.kind: asset})


@router.post("/admin/galgame/story-templates/{template_id}/assets", response_model=GalgameAssetGenerateResponse)
def generate_galgame_story_template_assets(
    template_id: str,
    payload: GalgameStoryTemplateAssetGenerateRequest,
    request: Request,
) -> GalgameAssetGenerateResponse:
    require_local_admin(request)
    try:
        template = session_service.get_galgame_story_template(template_id)
        assets = galgame_asset_service.generate_story_template_assets(
            background_key=template.background_key,
            background_prompt=template.background_prompt,
            character_key=template.character_key,
            character_prompt=template.character_prompt,
            include_character=payload.include_character,
            force=payload.force,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"galgame_asset_generation_failed: {exc}") from exc
    return GalgameAssetGenerateResponse(assets=assets)


@router.get("/admin/vector/templates/similar", response_model=VectorSearchResponse)
def similar_templates(
    request: Request,
    template_id: str | None = None,
    prompt: str | None = None,
    top_k: int | None = None,
) -> VectorSearchResponse:
    require_local_admin(request)
    if not template_id and not prompt:
        raise HTTPException(status_code=422, detail="template_id_or_prompt_required")

    template = None
    if template_id:
        template = next((item for item in session_service.list_items(include_archived=True) if item.id == template_id), None)
        if template is None:
            raise HTTPException(status_code=404, detail="template_not_found")
    hits = vector_indexer.search_similar_templates(template=template, prompt=prompt, top_k=top_k)
    return VectorSearchResponse(enabled=vector_indexer.is_enabled(), hits=hits)


@router.get("/admin/vector/sessions/similar", response_model=VectorSearchResponse)
def similar_sessions(
    request: Request,
    session_id: str,
    top_k: int | None = None,
) -> VectorSearchResponse:
    require_local_admin(request)
    try:
        session = session_service.get_session(session_id, force_reload=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    hits = vector_indexer.search_similar_sessions(session, top_k=top_k)
    return VectorSearchResponse(enabled=vector_indexer.is_enabled(), hits=hits)


@router.get("/admin/vector/galgame-turns/similar", response_model=VectorSearchResponse)
def similar_galgame_turns(
    request: Request,
    prompt: str,
    top_k: int | None = None,
) -> VectorSearchResponse:
    require_local_admin(request)
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="prompt_required")
    hits = vector_indexer.search_similar_galgame_turns(prompt=prompt, top_k=top_k)
    return VectorSearchResponse(enabled=vector_indexer.is_enabled(), hits=hits)


@router.get("/admin/vector/sync-failures", response_model=VectorSyncFailureResponse)
def vector_sync_failures(request: Request, limit: int = 25) -> VectorSyncFailureResponse:
    require_local_admin(request)
    return VectorSyncFailureResponse(items=local_session_store.list_vector_sync_failures(limit))


@router.post("/admin/item-template/create", response_model=ItemTemplateCreateResponse)
def create_item_template(payload: ItemTemplateCreateRequest, request: Request) -> ItemTemplateCreateResponse:
    require_local_admin(request)
    try:
        item = session_service.add_item(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ItemTemplateCreateResponse(item=QuestionResponse.from_item(item))


@router.put("/admin/item-template/{template_id}", response_model=ItemTemplateCreateResponse)
def update_item_template(template_id: str, payload: ItemTemplateCreateRequest, request: Request) -> ItemTemplateCreateResponse:
    require_local_admin(request)
    try:
        item = session_service.update_item(template_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ItemTemplateCreateResponse(item=QuestionResponse.from_item(item))


@router.get("/admin/templates", response_model=TemplateListResponse)
def list_templates(request: Request, include_archived: bool = False) -> TemplateListResponse:
    require_local_admin(request)
    return TemplateListResponse(items=[QuestionResponse.from_item(item) for item in session_service.list_items(include_archived)])


@router.get("/admin/item-instances", response_model=ItemInstanceListResponse)
def list_item_instances(request: Request, session_id: str | None = None) -> ItemInstanceListResponse:
    require_local_admin(request)
    items = session_service.list_item_instances(session_id)
    return ItemInstanceListResponse(items=[QuestionResponse.from_item(item) for item in items])


@router.get("/admin/sessions", response_model=SessionHistoryListResponse)
def list_sessions(request: Request) -> SessionHistoryListResponse:
    require_local_admin(request)
    return SessionHistoryListResponse(sessions=session_service.list_sessions())


@router.post("/admin/cleanup")
def cleanup_expired_sessions(request: Request) -> dict[str, int]:
    require_local_admin(request)
    removed = session_service.cleanup_expired()
    return {"removed": removed}


@router.get("/admin/clusters/overview", response_model=ClusterOverviewResponse)
def cluster_overview(request: Request) -> ClusterOverviewResponse:
    require_local_admin(request)
    return ClusterOverviewResponse(**session_service.cluster_overview().model_dump())


@router.post("/admin/clusters/label-override")
def save_cluster_label_override(payload: ClusterLabelOverrideRequest, request: Request) -> dict[str, bool]:
    require_local_admin(request)
    session_service.save_cluster_label_override(
        payload.version,
        payload.cluster_index,
        payload.name,
        payload.narrative_label,
    )
    return {"saved": True}


@router.post("/admin/item-template/{template_id}/archive", response_model=ItemTemplateCreateResponse)
def archive_item_template(template_id: str, request: Request) -> ItemTemplateCreateResponse:
    require_local_admin(request)
    try:
        item = session_service.archive_item(template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ItemTemplateCreateResponse(item=QuestionResponse.from_item(item))


@router.delete("/admin/item-template/{template_id}")
def delete_item_template(template_id: str, request: Request) -> dict[str, bool]:
    require_local_admin(request)
    try:
        session_service.delete_item(template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"deleted": True}
