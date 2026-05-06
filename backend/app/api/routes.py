"""Public API routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.schemas import (
    MapResponse,
    NextQuestionRequest,
    QuestionResponse,
    ReportGenerateRequest,
    ReportResponse,
    SessionSummaryResponse,
    StartSessionRequest,
    StartSessionResponse,
    SubmitResponseRequest,
    SubmitResponseResponse,
    WorkbenchEvidenceResponse,
)
from app.api.security import build_owner_key
from app.core.config import settings
from app.services.session_service import session_service

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


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/session/start", response_model=StartSessionResponse)
def start_session(payload: StartSessionRequest, request: Request) -> StartSessionResponse:
    session, item, access = session_service.start_session(
        mode=payload.mode,
        owner_key=build_owner_key(request),
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
