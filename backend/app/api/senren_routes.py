"""千恋万花监视器 API 路由"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse

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
