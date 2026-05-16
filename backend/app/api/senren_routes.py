"""千恋万花监视器 API 路由"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.domain.senren_choice_tree import ALL_CHOICES, ALL_ROUTES, get_choice_by_id
from app.domain.senren_dimension_mapping import (
    CHARACTER_PROFILES,
    CHOICE_DIMENSION_MAP,
    EXPANDED_SCENARIOS,
    get_all_mappings,
    get_mapping,
    get_mapping_for_choice,
)
from app.services.senren_monitor_service import senren_monitor_service

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
    """提交一个游戏选择

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
        return senren_monitor_service.submit_game_choice(session_id, choice_id, option_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
