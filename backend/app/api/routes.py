"""Public API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.schemas import (
    GalgameStoryTemplateListResponse,
    GalgameStoryTemplateRequest,
    GalgameStoryTemplateResponse,
    GalgameRespondRequest,
    GalgameSceneResponse,
    GalgameSceneResultResponse,
    MapResponse,
    NextQuestionRequest,
    QuestionResponse,
    RedeemInviteRequest,
    ReportGenerateRequest,
    ReportResponse,
    SessionSummaryResponse,
    StartSessionRequest,
    StartSessionResponse,
    SessionAccessIssueResponse,
    SubmitResponseRequest,
    SubmitResponseResponse,
    UserAccessResponse,
    UserEvolutionResponse,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserSessionListResponse,
    UserRecommendationResponse,
    WorkbenchEvidenceResponse,
)
from app.api.security import build_owner_key
from app.core.config import settings
from app.domain.models import GalgameStoryTemplate
from app.services.session_service import session_service
from app.services.user_service import user_service

router = APIRouter()


def _require_session_access(session_id: str, session_secret: str | None, request: Request) -> None:
    if not session_secret:
        raise HTTPException(status_code=401, detail="session_secret_required")
    try:
        session_service.authorize_session(session_id, session_secret, build_owner_key(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_delete_access(session_id: str, delete_token: str | None, request: Request) -> None:
    if not delete_token:
        raise HTTPException(status_code=401, detail="delete_token_required")
    try:
        session_service.authorize_session_delete(session_id, delete_token, build_owner_key(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_user(user_id: str | None, user_secret: str | None):
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id_required")
    try:
        return user_service.authenticate(user_id, user_secret)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/invite/redeem", response_model=UserAccessResponse)
def redeem_invite(payload: RedeemInviteRequest) -> UserAccessResponse:
    try:
        access = user_service.redeem_invite(payload.invite_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserAccessResponse(**access.model_dump())


@router.get("/user/me", response_model=UserProfileResponse)
def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> UserProfileResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return UserProfileResponse.from_profile(profile)


@router.patch("/user/me", response_model=UserProfileResponse)
def update_current_user(
    payload: UserProfileUpdateRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> UserProfileResponse:
    profile = _require_user(x_user_id, x_user_secret)
    updated = user_service.update_profile_flags(
        profile,
        relationship_opt_in=payload.relationship_opt_in,
        recommendation_opt_in=payload.recommendation_opt_in,
    )
    return UserProfileResponse.from_profile(updated)


@router.get("/user/sessions", response_model=UserSessionListResponse)
def list_user_sessions(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> UserSessionListResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return UserSessionListResponse(
        user=UserProfileResponse.from_profile(profile),
        sessions=session_service.list_sessions(user_id=profile.user_id),
    )


@router.get("/user/evolution", response_model=UserEvolutionResponse)
def get_user_evolution(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> UserEvolutionResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return UserEvolutionResponse(
        user=UserProfileResponse.from_profile(profile),
        items=session_service.build_user_evolution(profile.user_id),
    )


@router.get("/user/recommendations", response_model=UserRecommendationResponse)
def current_user_recommendations(
    limit: int = 5,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> UserRecommendationResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return UserRecommendationResponse(
        enabled=settings.relationship_recommendations_enabled,
        items=user_service.recommend_candidates(profile.user_id, limit),
    )


@router.post("/user/session/{session_id}/access", response_model=SessionAccessIssueResponse)
def issue_user_session_access(
    session_id: str,
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> SessionAccessIssueResponse:
    profile = _require_user(x_user_id, x_user_secret)
    try:
        record = session_service.get_session(session_id, force_reload=True)
        if record.user_id != profile.user_id:
            raise PermissionError("session_user_mismatch")
        access = session_service.issue_session_access(session_id, build_owner_key(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return SessionAccessIssueResponse(**access.model_dump())


@router.get("/user/galgame/story-templates", response_model=GalgameStoryTemplateListResponse)
def list_user_galgame_story_templates(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> GalgameStoryTemplateListResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return GalgameStoryTemplateListResponse(
        items=[
            GalgameStoryTemplateResponse(**template.model_dump())
            for template in session_service.list_galgame_story_templates(
                include_inactive=False,
                owner_user_id=profile.user_id,
                include_system=True,
            )
        ]
    )


@router.post("/user/galgame/story-templates", response_model=GalgameStoryTemplateResponse)
def create_user_galgame_story_template(
    payload: GalgameStoryTemplateRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> GalgameStoryTemplateResponse:
    profile = _require_user(x_user_id, x_user_secret)
    now = datetime.now(UTC)
    template = session_service.save_user_galgame_story_template(
        profile.user_id,
        GalgameStoryTemplate(
            template_id=f"user-story-{profile.user_id[:8]}-{uuid4().hex[:10]}",
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        ),
    )
    return GalgameStoryTemplateResponse(**template.model_dump())


@router.put("/user/galgame/story-templates/{template_id}", response_model=GalgameStoryTemplateResponse)
def update_user_galgame_story_template(
    template_id: str,
    payload: GalgameStoryTemplateRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> GalgameStoryTemplateResponse:
    profile = _require_user(x_user_id, x_user_secret)
    try:
        existing = session_service.get_galgame_story_template(template_id)
        if existing.owner_user_id != profile.user_id:
            raise PermissionError("galgame_story_template_owner_mismatch")
        template = session_service.save_user_galgame_story_template(
            profile.user_id,
            GalgameStoryTemplate(
                template_id=template_id,
                created_at=existing.created_at,
                updated_at=datetime.now(UTC),
                **payload.model_dump(),
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return GalgameStoryTemplateResponse(**template.model_dump())


@router.delete("/user/galgame/story-templates/{template_id}")
def delete_user_galgame_story_template(
    template_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> dict[str, bool]:
    profile = _require_user(x_user_id, x_user_secret)
    try:
        session_service.delete_user_galgame_story_template(profile.user_id, template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"deleted": True}


@router.post("/session/start", response_model=StartSessionResponse)
def start_session(
    payload: StartSessionRequest,
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> StartSessionResponse:
    profile = None
    if x_user_id or x_user_secret:
        profile = _require_user(x_user_id, x_user_secret)
    session, item, access = session_service.start_session(
        mode=payload.mode,
        owner_key=build_owner_key(request),
        user_id=profile.user_id if profile else None,
    )
    return StartSessionResponse(
        session_id=session.session_id,
        session_secret=access.session_secret,
        delete_token=access.delete_token,
        state=session.state,
        question=QuestionResponse.from_item(item),
        workbench_checkpoint=session_service.build_workbench_checkpoint(session.session_id),
    )


@router.post("/question/next", response_model=QuestionResponse)
def next_question(
    payload: NextQuestionRequest,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> QuestionResponse:
    _require_session_access(payload.session_id, x_session_secret, request)
    try:
        item = session_service.get_next_question(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return QuestionResponse.from_item(item)


@router.post("/response/submit", response_model=SubmitResponseResponse)
def submit_response(
    payload: SubmitResponseRequest,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> SubmitResponseResponse:
    _require_session_access(payload.session_id, x_session_secret, request)
    try:
        session, next_item = session_service.submit_answer(
            payload.session_id,
            payload.item_id,
            payload.option_key,
            payload.latency_ms,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SubmitResponseResponse(
        session_id=session.session_id,
        state=session.state,
        can_generate_report=session.state.question_count >= settings.min_questions_for_report,
        remaining_until_report=max(settings.min_questions_for_report - session.state.question_count, 0),
        next_question=QuestionResponse.from_item(next_item) if next_item else None,
        workbench_checkpoint=session_service.build_workbench_checkpoint(session.session_id),
    )


@router.get("/session/{session_id}/summary", response_model=SessionSummaryResponse)
def get_summary(
    session_id: str,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> SessionSummaryResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        summary = session_service.build_summary(session_id)
        current_question = session_service.get_current_question(session_id)
        return SessionSummaryResponse(
            **summary.model_dump(),
            current_question=QuestionResponse.from_item(current_question) if current_question else None,
            workbench_checkpoint=session_service.build_workbench_checkpoint(session_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/session/{session_id}/workbench/evidence", response_model=WorkbenchEvidenceResponse)
def get_workbench_evidence(
    session_id: str,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> WorkbenchEvidenceResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        return session_service.build_workbench_evidence(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/session/{session_id}/galgame/scene", response_model=GalgameSceneResponse)
def get_galgame_scene(
    session_id: str,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> GalgameSceneResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        return session_service.build_galgame_scene(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/session/{session_id}/galgame/respond", response_model=GalgameSceneResultResponse)
def respond_galgame_scene(
    session_id: str,
    payload: GalgameRespondRequest,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> GalgameSceneResultResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        text_inference = session_service.record_galgame_turn(
            session_id=session_id,
            item_id=payload.item_id,
            scene_id=payload.scene_id,
            option_key=payload.option_key,
            choice_text=payload.choice_text,
            custom_text=payload.custom_text,
        )
        resolved_option_key = payload.option_key
        if (
            payload.custom_text
            and text_inference.inferred_option_key
            and text_inference.confidence >= settings.galgame_free_text_inference_min_confidence
        ):
            resolved_option_key = text_inference.inferred_option_key
        session, next_item = session_service.submit_answer(
            session_id,
            payload.item_id,
            resolved_option_key,
            payload.latency_ms,
        )
        next_scene = session_service.build_galgame_scene(session_id) if next_item else None
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GalgameSceneResultResponse(
        session_id=session.session_id,
        state=session.state,
        can_generate_report=session.state.question_count >= settings.min_questions_for_report,
        remaining_until_report=max(settings.min_questions_for_report - session.state.question_count, 0),
        scene=next_scene,
        text_inference=text_inference,
        workbench_checkpoint=session_service.build_workbench_checkpoint(session.session_id),
    )


@router.get("/session/{session_id}/report", response_model=ReportResponse)
def get_report(
    session_id: str,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> ReportResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        return session_service.build_report(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/session/{session_id}/report", response_model=ReportResponse)
def generate_report(
    session_id: str,
    payload: ReportGenerateRequest,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> ReportResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        return session_service.build_report(session_id, naming_style=payload.naming_style)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/session/{session_id}/map", response_model=MapResponse)
def get_map(
    session_id: str,
    request: Request,
    projection_mode: str = "auto",
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> MapResponse:
    _require_session_access(session_id, x_session_secret, request)
    try:
        payload = session_service.build_map(session_id, projection_mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MapResponse(**payload)


@router.delete("/session/{session_id}")
def discard_session(
    session_id: str,
    request: Request,
    x_delete_token: str | None = Header(default=None, alias="X-Delete-Token"),
) -> dict[str, bool]:
    _require_delete_access(session_id, x_delete_token, request)
    try:
        session_service.discard_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True}
