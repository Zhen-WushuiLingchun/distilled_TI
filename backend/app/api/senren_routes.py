"""千恋万花监视器 API 路由"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.schemas import (
    SenrenCompanionChoiceRequest,
    SenrenCompanionChoiceResponse,
    SenrenCompanionEventRequest,
    SenrenCompanionEventResponse,
    SenrenCompanionReportResponse,
    SenrenCompanionSessionListResponse,
    SenrenCompanionStartRequest,
    SenrenCompanionStartResponse,
)
from app.core.config import settings
from app.domain.models import ContextAnalysisMessage, SenrenCompanionChoice, SenrenCompanionEvent, SenrenCompanionSessionRecord
from app.domain.senren_choice_tree import ALL_CHOICES, ALL_ROUTES, get_choice_by_id
from app.domain.senren_dimension_mapping import (
    CHARACTER_PROFILES,
    CHOICE_DIMENSION_MAP,
    EXPANDED_SCENARIOS,
    get_all_mappings,
    get_mapping,
    get_mapping_for_choice,
)
from app.services.context_analysis_service import context_analysis_service
from app.services.senren_monitor_service import senren_monitor_service
from app.services.storage import local_session_store
from app.services.user_service import user_service

router = APIRouter(prefix="/api/senren")


def _require_session(session_id: str, session_secret: str | None):
    if not session_secret:
        raise HTTPException(status_code=401, detail="session_secret_required")
    try:
        return senren_monitor_service.authorize(session_id, session_secret)
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


def _require_companion_record(session_id: str, user_id: str) -> SenrenCompanionSessionRecord:
    record = local_session_store.load_senren_companion_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="senren_companion_session_not_found")
    if record.user_id != user_id:
        raise HTTPException(status_code=403, detail="senren_companion_session_user_mismatch")
    return record


# ============================================================
# 监视器会话
# ============================================================

@router.post("/monitor/start")
def start_monitor(
    request: Request,
    mode: str = "monitor",
) -> dict:
    """启动一次千恋万花监视会话

    mode:
      - "monitor": 实时监视模式（追踪游戏选择）
      - "story": 独立故事模式（视觉小说风格答题）
    """
    result = senren_monitor_service.start_session(
        mode=mode,
        owner_key=request.client.host if request.client else "",
    )
    return result


@router.get("/monitor/{session_id}/live-state")
def get_live_state(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取实时人格画像状态"""
    _require_session(session_id, x_session_secret)
    return senren_monitor_service.get_live_state(session_id)


@router.post("/monitor/choice")
def submit_choice(
    payload: dict,
    request: Request,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """提交一个游戏选择，并通过 Context API 进行人格测量

    请求体:
    {
        "session_id": "abc123",
        "choice_id": "senren-c1",
        "option_key": "honest"
    }
    """
    session_id = payload.get("session_id", "")
    choice_id = payload.get("choice_id", "")
    option_key = payload.get("option_key", "")

    if not all([session_id, choice_id, option_key]):
        raise HTTPException(status_code=422, detail="session_id, choice_id, option_key 均为必填")

    _require_session(session_id, x_session_secret)

    try:
        result = senren_monitor_service.submit_game_choice(session_id, choice_id, option_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 通过 Context API 进行人格测量分析
    choice_recorded = result.get("choice_recorded", {})
    choice_context = choice_recorded.get("context", "")
    option_text = choice_recorded.get("option_text", "")
    location = choice_recorded.get("location", "")
    characters = choice_recorded.get("characters", [])

    try:
        context_analysis_service.analyze(
            application_id="senren-monitor",
            external_user_id=session_id,
            conversation_id=f"{session_id}-choices",
            messages=[
                ContextAnalysisMessage(
                    role="assistant",
                    content=f"[千恋万花游戏场景] 地点: {location}。角色: {', '.join(characters) if characters else '无'}。情境: {choice_context}",
                ),
                ContextAnalysisMessage(
                    role="user",
                    content=f"玩家选择了: {option_text}",
                ),
            ],
            consent_basis="user participating in Senren Banka personality monitor",
            channel="game_choice",
            locale="zh-CN",
            persist=True,
            persist_messages=False,
        )
    except Exception:
        pass  # Context API 分析失败不影响主流程

    return result


# ============================================================
# 路线图
# ============================================================

@router.get("/monitor/{session_id}/roadmap")
def get_roadmap(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取选择路线图及进度"""
    _require_session(session_id, x_session_secret)
    return senren_monitor_service.get_roadmap(session_id)


@router.get("/monitor/{session_id}/vn-scene")
def get_vn_scene(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取当前可游玩的 VN 场景。

    该接口会把 Senren 选择节点、角色 skills、历史选择和现有 DeepSeek-compatible
    AI 配置组合成前端可直接渲染的视觉小说 scene。AI 不可用时返回规则 fallback。
    """
    _require_session(session_id, x_session_secret)
    return senren_monitor_service.get_vn_scene(session_id)


@router.get("/monitor/{session_id}/asset/{asset_id}")
def get_monitor_asset(
    session_id: str,
    asset_id: str,
) -> FileResponse:
    """Serve a registered local/generated VN asset for the active session.

    The asset id is only created by the scene endpoint and is resolved against
    the session's approved game directory or ignored local character asset dirs.
    """
    try:
        asset_path = senren_monitor_service.resolve_local_asset(session_id, asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return FileResponse(asset_path)


@router.get("/roadmap")
def get_full_roadmap() -> dict:
    """获取完整路线图（无需会话）"""
    return {
        "nodes": [
            {
                "choice_id": c.choice_id,
                "chapter": c.chapter,
                "location": c.location,
                "characters": c.characters,
                "context": c.context,
                "prompt": c.prompt,
                "options": [
                    {"key": o.key, "text": o.text, "affection_target": o.affection_target}
                    for o in c.options
                ],
                "mappings": [
                    {
                        "option_key": m.option_key,
                        "dimension_weights": m.dimension_weights,
                        "scenario_tags": m.scenario_tags,
                    }
                    for m in get_mapping_for_choice(c.choice_id)
                ],
            }
            for c in ALL_CHOICES
        ],
        "routes": {
            route_id: {
                "name": route["route_name"],
                "entry_conditions": route["entry_conditions"],
                "description": route["description"],
            }
            for route_id, route in ALL_ROUTES.items()
        },
        "characters": {
            name: profile for name, profile in CHARACTER_PROFILES.items()
        },
        "total_available_options": len(get_all_mappings()),
    }


# ============================================================
# 报告
# ============================================================

@router.get("/monitor/{session_id}/report")
def get_report(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """生成千恋万花人格报告"""
    _require_session(session_id, x_session_secret)
    try:
        return senren_monitor_service.generate_report(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/monitor/{session_id}/report")
def generate_report_with_style(
    session_id: str,
    payload: dict,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """生成报告（支持参数）"""
    _require_session(session_id, x_session_secret)
    try:
        return senren_monitor_service.generate_report(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ============================================================
# 角色契合度
# ============================================================

@router.get("/monitor/{session_id}/character-affinity")
def get_character_affinity(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取角色契合度分析"""
    session = _require_session(session_id, x_session_secret)
    from app.domain.senren_dimension_mapping import compute_character_affinity

    affinity = compute_character_affinity(session.state.core_mu)

    # 各维度上的比较
    dimension_comparison = {}
    best_match = max(affinity, key=affinity.get) if affinity else None
    if best_match and best_match in CHARACTER_PROFILES:
        char_profile = CHARACTER_PROFILES[best_match]
        dimension_comparison = {
            dim: {
                "you": round(session.state.core_mu.get(dim, 0), 2),
                f"{best_match}": round(char_profile.get(dim, 0), 2),
            }
            for dim in char_profile
        }

    return {
        "affinity": affinity,
        "best_match": best_match,
        "dimension_comparison": dimension_comparison,
        "all_profiles": CHARACTER_PROFILES,
    }


# ============================================================
# 会话管理
# ============================================================

@router.get("/sessions")
def list_sessions() -> dict:
    """列出所有监视会话"""
    return {"sessions": senren_monitor_service.list_sessions()}


@router.delete("/monitor/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    x_delete_token: str | None = Header(default=None, alias="X-Delete-Token"),
) -> dict:
    """删除监视会话"""
    if not x_delete_token:
        raise HTTPException(status_code=401, detail="delete_token_required")
    session = senren_monitor_service.get_session(session_id)
    if session.delete_token != x_delete_token:
        raise HTTPException(status_code=403, detail="delete_token_mismatch")
    senren_monitor_service.delete_session(session_id)
    return {"deleted": True}


# ============================================================
# 本地 Companion 同步 API
# ============================================================

@router.post("/companion/start", response_model=SenrenCompanionStartResponse)
def start_companion_session(
    payload: SenrenCompanionStartRequest,
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> SenrenCompanionStartResponse:
    """由本机 companion 启动一条用户绑定的 Senren 测量记录。"""
    profile = _require_user(x_user_id, x_user_secret)
    result = senren_monitor_service.start_session(
        mode="local_companion",
        owner_key=request.client.host if request.client else "",
        user_id=profile.user_id,
    )
    now = datetime.now(UTC)
    record = SenrenCompanionSessionRecord(
        session_id=result["session_id"],
        user_id=profile.user_id,
        handle=profile.handle,
        client_id=payload.client_id,
        game_title=payload.game_title,
        game_path=payload.game_path,
        game_path_fingerprint=payload.game_path_fingerprint,
        game_info=payload.game_info,
        choices_count=0,
        state_snapshot=result.get("state", {}),
        created_at=now,
        updated_at=now,
    )
    local_session_store.save_senren_companion_session(record)
    return SenrenCompanionStartResponse(
        session_id=result["session_id"],
        session_secret=result["session_secret"],
        delete_token=result["delete_token"],
        roadmap=result.get("roadmap", {}),
        total_choices=int(result.get("total_choices", 0)),
        record=record,
    )


@router.get("/companion/sessions", response_model=SenrenCompanionSessionListResponse)
def list_companion_sessions(
    limit: int = 50,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> SenrenCompanionSessionListResponse:
    profile = _require_user(x_user_id, x_user_secret)
    return SenrenCompanionSessionListResponse(
        items=local_session_store.list_senren_companion_sessions(profile.user_id, limit=limit)
    )


@router.get("/companion/{session_id}", response_model=SenrenCompanionSessionRecord)
def get_companion_session(
    session_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> SenrenCompanionSessionRecord:
    profile = _require_user(x_user_id, x_user_secret)
    return _require_companion_record(session_id, profile.user_id)


@router.post("/companion/{session_id}/choice", response_model=SenrenCompanionChoiceResponse)
def submit_companion_choice(
    session_id: str,
    payload: SenrenCompanionChoiceRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> SenrenCompanionChoiceResponse:
    profile = _require_user(x_user_id, x_user_secret)
    record = _require_companion_record(session_id, profile.user_id)
    _require_session(session_id, x_session_secret)
    try:
        result = senren_monitor_service.submit_game_choice(session_id, payload.choice_id, payload.option_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    choice_recorded = result.get("choice_recorded", {})
    try:
        choice = SenrenCompanionChoice.model_validate(choice_recorded)
    except Exception:
        choice = SenrenCompanionChoice(
            choice_id=payload.choice_id,
            option_key=payload.option_key,
            timestamp=datetime.now(UTC),
        )
    choice = choice.model_copy(
        update={
            "choice_text": payload.choice_text or choice.option_text,
            "option_text": payload.choice_text or choice.option_text,
            "dialogue_text": payload.dialogue_text,
            "scene_title": payload.scene_title,
            "context": payload.dialogue_text or choice.context,
        }
    )
    updated = record.model_copy(
        update={
            "choices": [*record.choices, choice],
            "choices_count": int(result.get("total_choices_made", record.choices_count + 1)),
            "current_route": result.get("current_route"),
            "state_snapshot": result.get("state", {}),
            "updated_at": datetime.now(UTC),
        }
    )
    local_session_store.save_senren_companion_session(updated)

    try:
        context_analysis_service.analyze(
            application_id="senren-companion",
            external_user_id=profile.user_id,
            conversation_id=f"senren-companion-{session_id}",
            messages=[
                ContextAnalysisMessage(
                    role="assistant",
                    content=(
                        f"[Senren companion scene] 地点: {choice.location or '未知'}。"
                        f"角色: {', '.join(choice.characters) if choice.characters else '未知'}。"
                        f"场景: {choice.scene_title or payload.choice_id}。"
                        f"上下文: {choice.dialogue_text or choice.context or payload.choice_id}"
                    ),
                ),
                ContextAnalysisMessage(role="user", content=f"玩家选择了: {choice.choice_text or choice.option_text or payload.option_key}"),
            ],
            consent_basis="user logged in and connected a local Senren companion for game-choice analysis",
            channel="local_game_choice",
            locale="zh-CN",
            metadata={"session_id": session_id, "choice_id": payload.choice_id, "option_key": payload.option_key},
            persist=True,
            persist_messages=False,
        )
    except Exception:
        pass

    return SenrenCompanionChoiceResponse(
        record=updated,
        state=result.get("state", {}),
        choice_recorded=choice_recorded,
        total_choices_made=int(result.get("total_choices_made", updated.choices_count)),
        current_route=result.get("current_route"),
        can_generate_report=bool(result.get("can_generate_report", False)),
        remaining_until_report=int(result.get("remaining_until_report", 0)),
    )


_COMPANION_EVENT_TYPES = {"scene_text", "choice_snapshot", "route_marker", "heartbeat"}
_COMPANION_EVENT_SOURCES = {"manual", "hook", "ocr", "clipboard", "save_parser"}
_MAX_COMPANION_EVENTS_PER_SESSION = 500


@router.post("/companion/{session_id}/event", response_model=SenrenCompanionEventResponse)
def submit_companion_event(
    session_id: str,
    payload: SenrenCompanionEventRequest,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> SenrenCompanionEventResponse:
    """Record a local companion/hook event without advancing the measurement route.

    The game directory, XP3 archive and hook implementation stay on the user's
    machine. This endpoint only receives the authorized local client's text
    snapshot, visible choices or route marker for later analysis/report context.
    """
    profile = _require_user(x_user_id, x_user_secret)
    record = _require_companion_record(session_id, profile.user_id)
    _require_session(session_id, x_session_secret)

    event_type = payload.event_type if payload.event_type in _COMPANION_EVENT_TYPES else "scene_text"
    source = payload.source if payload.source in _COMPANION_EVENT_SOURCES else "manual"
    visible_choices = [choice[:500] for choice in payload.visible_choices[:12] if choice.strip()]
    event = SenrenCompanionEvent(
        event_id=f"senren-event-{uuid4().hex}",
        event_type=event_type,  # type: ignore[arg-type]
        scene_title=payload.scene_title,
        dialogue_text=payload.dialogue_text,
        visible_choices=visible_choices,
        route_marker=payload.route_marker,
        source=source,  # type: ignore[arg-type]
        metadata=payload.metadata,
    )
    events = [*record.events, event][-_MAX_COMPANION_EVENTS_PER_SESSION:]
    updated = record.model_copy(
        update={
            "events": events,
            "updated_at": datetime.now(UTC),
        }
    )
    local_session_store.save_senren_companion_session(updated)

    if event.dialogue_text or event.visible_choices:
        try:
            context_analysis_service.analyze(
                application_id="senren-companion",
                external_user_id=profile.user_id,
                conversation_id=f"senren-companion-{session_id}",
                messages=[
                    ContextAnalysisMessage(
                        role="assistant",
                        content=(
                            f"[Senren local event] 来源: {event.source}。"
                            f"场景: {event.scene_title or event.route_marker or '未知'}。"
                            f"文本: {event.dialogue_text or '无'}。"
                            f"可见选项: {' / '.join(event.visible_choices) if event.visible_choices else '无'}"
                        ),
                    )
                ],
                consent_basis="user logged in and connected a local Senren companion for game-context analysis",
                channel="local_game_event",
                locale="zh-CN",
                metadata={"session_id": session_id, "event_id": event.event_id, "event_type": event.event_type},
                persist=True,
                persist_messages=False,
            )
        except Exception:
            pass

    return SenrenCompanionEventResponse(
        record=updated,
        event=event,
        stored_events_count=len(updated.events),
    )


@router.get("/companion/{session_id}/report", response_model=SenrenCompanionReportResponse)
def get_companion_report(
    session_id: str,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_secret: str | None = Header(default=None, alias="X-User-Secret"),
) -> SenrenCompanionReportResponse:
    profile = _require_user(x_user_id, x_user_secret)
    record = _require_companion_record(session_id, profile.user_id)
    try:
        report = senren_monitor_service.generate_report(session_id)
    except KeyError:
        if record.report_snapshot is None:
            raise HTTPException(status_code=409, detail="senren_companion_runtime_session_missing")
        report = record.report_snapshot
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    updated = record.model_copy(
        update={
            "report_snapshot": report,
            "status": "completed",
            "updated_at": datetime.now(UTC),
        }
    )
    local_session_store.save_senren_companion_session(updated)
    return SenrenCompanionReportResponse(record=updated, report=report)


# ============================================================
# 扩展场景（独立故事模式用）
# ============================================================

@router.get("/monitor/{session_id}/next-scenario")
def get_next_scenario(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取下一个扩展场景"""
    _require_session(session_id, x_session_secret)
    result = senren_monitor_service.get_next_scenario(session_id)
    if result is None:
        return {"completed": True, "message": "所有场景已完成"}
    return {"completed": False, **result}


# ============================================================
# 本地游戏模式
# ============================================================

VALID_GAME_FILES = [
    "scenario.pck",
    "Script.pck",
    "千恋＊万花.exe",
    "SenrenBanka.exe",
]
VALID_GAME_DIRS = ["data", "savedata"]


def _validate_game_path(game_path: str) -> dict:
    """校验本地千恋万花安装目录"""
    path = Path(game_path)
    if not path.exists():
        return {
            "valid": False,
            "error": f"路径不存在: {game_path}",
            "found_files": [],
            "missing_files": VALID_GAME_FILES,
            "found_dirs": [],
            "skill_count": _senren_skill_count(),
            "asset_summary": _senren_asset_summary(game_path),
            "integration_mode": "manual_companion_vn",
        }

    found_files = []
    missing_files = []
    for f in VALID_GAME_FILES:
        target = path / f
        # 也检查子目录
        found = target.exists()
        if not found:
            # 检查一级子目录
            for child in path.iterdir():
                if child.is_dir() and (child / f).exists():
                    found = True
                    break
        if found:
            found_files.append(f)
        else:
            missing_files.append(f)

    found_dirs = [d for d in VALID_GAME_DIRS if (path / d).exists()]

    # 至少需要一个关键文件
    is_valid = len(found_files) >= 1

    return {
        "valid": is_valid,
        "path": str(path.absolute()),
        "found_files": found_files,
        "missing_files": missing_files,
        "found_dirs": found_dirs,
        "skill_count": _senren_skill_count(),
        "asset_summary": _senren_asset_summary(game_path),
        "integration_mode": "manual_companion_vn",
        "capabilities": [
            "validate_local_game_directory",
            "play_web_vn_companion",
            "load_character_skills",
            "deepseek_scene_enrichment",
            "record_route_choices",
        ],
        "hint": "目录有效，可启动监视" if is_valid else f"未找到千恋万花关键文件。找到: {found_files}，缺失: {missing_files}",
    }


def _senren_skill_count() -> int:
    try:
        from app.domain.senren_skills_loader import get_all_personas_cached

        return len(get_all_personas_cached())
    except Exception:
        return 0


def _senren_asset_summary(game_path: str | None = None) -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    generated_root = repo_root / "frontend" / "public" / "generated" / "galgame"
    static_root = repo_root / "frontend" / "public" / "galgame-assets"

    def count_images(root: Path, folder: str) -> int:
        target = root / folder
        if not target.exists():
            return 0
        return sum(1 for item in target.iterdir() if item.is_file())

    summary = {
        "generated_backgrounds": count_images(generated_root, "background"),
        "generated_characters": count_images(generated_root, "character"),
        "fallback_backgrounds": count_images(static_root, "backgrounds"),
        "fallback_sprites": count_images(static_root, "sprites"),
    }
    if game_path:
        summary.update(senren_monitor_service.local_visual_asset_summary(game_path))
    return summary


@router.post("/local-game/validate")
def validate_local_game(payload: dict) -> dict:
    """校验本地千恋万花路径

    请求体: {"game_path": "D:/games/千恋万花"}
    """
    game_path = payload.get("game_path", "")
    if not game_path:
        raise HTTPException(status_code=422, detail="game_path 为必填")
    return _validate_game_path(game_path)


@router.post("/local-game/start")
def start_local_game_monitor(
    payload: dict,
    request: Request,
) -> dict:
    """启动本地千恋万花监视会话

    请求体: {"game_path": "D:/games/千恋万花", "mode": "local"}
    """
    game_path = payload.get("game_path", "")
    if not game_path:
        raise HTTPException(status_code=422, detail="game_path 为必填")

    validation = _validate_game_path(game_path)
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail=validation["hint"])

    mode = payload.get("mode", "local")
    result = senren_monitor_service.start_session(
        mode=mode,
        owner_key=request.client.host if request.client else "",
    )

    # 将游戏路径附加到会话
    session = senren_monitor_service.get_session(result["session_id"])
    session.game_path = str(Path(game_path).absolute())
    session.game_info = validation
    local_assets = senren_monitor_service.attach_local_visual_assets(session, session.game_path)
    session.game_info = {
        **validation,
        "asset_summary": {
            **validation.get("asset_summary", {}),
            "local_game_images": len(local_assets.get("all", [])),
            "local_background_candidates": len(local_assets.get("backgrounds", [])),
            "local_character_candidates": len(local_assets.get("characters", [])),
        },
    }

    return {
        **result,
        "game_path": session.game_path,
        "game_info": session.game_info,
    }


@router.get("/local-game/{session_id}/info")
def get_local_game_info(
    session_id: str,
    x_session_secret: str | None = Header(default=None, alias="X-Session-Secret"),
) -> dict:
    """获取本地游戏监视信息"""
    session = _require_session(session_id, x_session_secret)
    game_path = getattr(session, "game_path", None)
    if not game_path:
        raise HTTPException(status_code=404, detail="此会话不是本地游戏模式")

    game_info = getattr(session, "game_info", _validate_game_path(game_path))
    return {
        "session_id": session_id,
        "game_path": game_path,
        "game_info": game_info,
        "choices_made": len(session.choices_made),
        "current_route": session.current_route,
    }


_KIRIKIRI_EXE_NAMES = [
    "SenrenBanka.exe",
    "千恋＊万花.exe",
    "千恋万花.exe",
    "krkr.exe",
    "kirikiri.exe",
    "kirikiroid2.exe",
]


def _find_game_exe(game_path: str) -> str | None:
    """在游戏目录中查找可执行文件"""
    root = Path(game_path)
    if not root.exists():
        return None
    # 优先精确匹配
    for name in _KIRIKIRI_EXE_NAMES:
        candidate = root / name
        if candidate.is_file():
            return str(candidate)
    # 退而求其次，查找任意 exe
    for item in root.iterdir():
        if item.is_file() and item.suffix.lower() == ".exe":
            return str(item)
    return None


@router.post("/local-game/launch")
def launch_local_game(
    payload: dict,
    request: Request,
) -> dict:
    """启动本地千恋万花游戏并开始监视

    请求体: {"game_path": "D:/games/千恋万花"}
    """
    game_path = payload.get("game_path", "")
    if not game_path:
        raise HTTPException(status_code=422, detail="game_path 为必填")

    validation = _validate_game_path(game_path)
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail=validation["hint"])

    exe_path = _find_game_exe(game_path)
    if not exe_path:
        raise HTTPException(
            status_code=422,
            detail=f"在 {game_path} 中未找到游戏可执行文件。请确认目录中包含 SenrenBanka.exe 或千恋＊万花.exe。",
        )

    # 启动监视会话
    result = senren_monitor_service.start_session(
        mode="local",
        owner_key=request.client.host if request.client else "",
    )
    session = senren_monitor_service.get_session(result["session_id"])
    session.game_path = str(Path(game_path).absolute())
    session.game_info = validation
    local_assets = senren_monitor_service.attach_local_visual_assets(session, session.game_path)

    # 启动游戏进程
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [exe_path],
                cwd=str(Path(exe_path).parent),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [exe_path],
                cwd=str(Path(exe_path).parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        session.game_info = {
            **validation,
            "exe_launched": exe_path,
            "launch_status": "started",
        }
    except Exception as exc:
        session.game_info = {
            **validation,
            "exe_launched": exe_path,
            "launch_status": f"failed: {exc}",
        }

    return {
        **result,
        "game_path": session.game_path,
        "game_info": session.game_info,
        "exe_launched": exe_path,
    }


# ============================================================
# Skills 人设 API（给前端 storymode 用）
# ============================================================

@router.get("/skills/personas")
def get_all_skills_personas() -> dict:
    """获取所有千恋万花角色的 skills 人设数据"""
    from app.domain.senren_skills_loader import get_all_personas_cached

    personas = get_all_personas_cached()
    # 精简返回——只返回前端需要的字段
    result = {}
    for slug, p in personas.items():
        result[slug] = {
            "display_name": p.get("display_name", slug),
            "profile": p.get("profile", {}),
            "impression": p.get("impression", ""),
            "tags": p.get("tags", {}).get("personality", []),
            "layer0": p.get("layer0", []),
            "layer2": {
                "tone": p.get("layer2", {}).get("tone", ""),
                "patterns": p.get("layer2", {}).get("patterns", [])[:4],
                "voice_sample": p.get("layer2", {}).get("voice_sample", ""),
                "emotional_tells": p.get("layer2", {}).get("emotional_tells", ""),
                "speaking_pace": p.get("layer2", {}).get("speaking_pace", ""),
            },
            "layer3": {
                "priorities": p.get("layer3", {}).get("priorities", ""),
                "enthusiasm": p.get("layer3", {}).get("enthusiasm", []),
                "caution": p.get("layer3", {}).get("caution", []),
            },
            "layer5": {
                "excited_by": p.get("layer5", {}).get("excited_by", []),
                "avoids": p.get("layer5", {}).get("avoids", []),
                "dislikes": p.get("layer5", {}).get("dislikes", []),
            },
            "personality_traits": p.get("personality_traits", {}),
        }
    return {"personas": result, "count": len(result)}


@router.get("/skills/personas/{slug}")
def get_one_persona(slug: str) -> dict:
    """获取单个角色的 skills 人设"""
    from app.domain.senren_skills_loader import load_character_persona

    persona = load_character_persona(slug)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"角色不存在: {slug}")
    return {"slug": slug, **persona}


@router.get("/skills/character-context/{slug}")
def get_character_context(slug: str) -> dict:
    """获取角色对话上下文提示词（给 AI 用）"""
    from app.domain.senren_skills_loader import get_character_speech_context

    ctx = get_character_speech_context(slug)
    if not ctx:
        raise HTTPException(status_code=404, detail=f"角色不存在: {slug}")
    return {"slug": slug, "context": ctx}


@router.get("/skills/storymode-enrichment")
def get_storymode_enrichment(characters: str = "") -> dict:
    """为 storymode 场景提供角色人设富化

    Query: ?characters=芳乃,茉子,将臣
    """
    from app.domain.senren_skills_loader import get_storymode_character_enrichment

    char_list = [c.strip() for c in characters.split(",") if c.strip()]
    if not char_list:
        return {"enrichment": {}, "message": "请提供 characters 参数"}

    enrichment = get_storymode_character_enrichment(char_list)
    return {"enrichment": enrichment, "count": len(enrichment)}
