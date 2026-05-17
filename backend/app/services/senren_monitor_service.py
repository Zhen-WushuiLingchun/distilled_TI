"""千恋万花 游戏选择人格监视器服务

在 Distilled TI 评分引擎之上封装游戏选择追踪逻辑：
- 将游戏选择（choice_id + option_key）转换为评分引擎可消费的 ItemTemplate
- 追踪选择进度、路线分析
- 计算角色契合度
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.domain.dimensions import (
    CORE_DIMENSION_LABELS,
    CORE_DIMENSION_KEYS,
    MODULE_LABELS,
    MODULE_KEYS,
    SUBDIMENSION_LABELS,
    SUBDIMENSION_TO_PARENT,
    make_zero_module_vector,
    make_zero_subdimension_vector,
    make_zero_vector,
)
from app.domain.models import (
    AnswerRecord,
    ItemInstance,
    ItemTemplate,
    QuestionOption,
    SessionReport,
    SessionState,
    StructuralLabel,
)
from app.domain.senren_choice_tree import (
    ALL_CHOICES,
    ALL_ROUTES,
    CHOICE_BY_ID,
    GameChoiceNode,
)
from app.domain.senren_dimension_mapping import (
    CHARACTER_PROFILES,
    CHOICE_DIMENSION_MAP,
    EXPANDED_SCENARIOS,
    ChoiceDimensionMapping,
    compute_character_affinity,
    get_all_mappings,
    get_mapping,
)
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.clustering import clustering_service
from app.services.reporting import (
    build_module_insights,
    build_subdimension_insights,
    render_narrative_label,
)
from app.services.scoring import ScoringEngine

# 游戏主题叙事标签覆盖
SENREN_NARRATIVE_LABELS = {
    "协同推进簇": "守护羁绊的剑士",
    "抽象统筹簇": "解读神话的巫女",
    "稳态执行簇": "在风暴中镇定的宿屋主人",
    "探索扩张簇": "开拓新羁绊的旅人",
    "强压决断簇": "斩断宿命的太刀",
    "情境适配簇": "穿梭于异界的付丧神",
}

SENREN_BACKGROUND_ASSETS = {
    "senren-c1": "/generated/galgame/background/old_school_corridor_afternoon.png",
    "senren-c2": "/generated/galgame/background/old_building_corridor_dusk.png",
    "senren-c3": "/generated/galgame/background/old_teaching_building_corridor.png",
    "senren-c4": "/generated/galgame/background/student_council_room_afternoon.png",
    "senren-c4a": "/generated/galgame/background/old_school_corridor_night.png",
    "senren-c5": "/generated/galgame/background/old_building_corridor_night.png",
    "senren-c6": "/generated/galgame/background/rooftop_dusk_tension.png",
    "senren-c7": "/generated/galgame/background/rooftop_iron_door_twilight.png",
}

SENREN_CHARACTER_ASSETS = {
    "芳乃": "/generated/galgame/character/transfer_student_conflict.png",
    "丛雨": "/generated/galgame/character/classmate_androgynous_calm.png",
    "茉子": "/generated/galgame/character/classmate_neutral.png",
    "蕾娜": "/generated/galgame/character/transfer_student_smirk.png",
    "小春": "/generated/galgame/character/classmate_closeup.png",
    "芦花": "/generated/galgame/character/companion_portrait.png",
}


LOCAL_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
LOCAL_ASSET_SCAN_LIMIT = 5000
LOCAL_ASSET_SKIP_PARTS = {"savedata", "save", "cache", "temp", "tmp", "movies", "video"}
LOCAL_BACKGROUND_KEYWORDS = {
    "background",
    "back",
    "bg",
    "haikei",
    "scene",
    "event",
    "cg",
    "room",
    "school",
    "corridor",
    "hall",
    "hallway",
    "rooftop",
    "class",
    "street",
    "shrine",
    "onsen",
    "ryokan",
    "kitchen",
    "garden",
    "背景",
    "场景",
}
LOCAL_CHARACTER_KEYWORDS = {
    "character",
    "char",
    "sprite",
    "stand",
    "tachie",
    "face",
    "body",
    "pose",
    "heroine",
    "立绘",
    "立ち",
}


class SenrenMonitorSession:
    """一次千恋万花监视会话的状态"""

    def __init__(
        self,
        session_id: str,
        session_secret: str,
        delete_token: str,
        mode: str = "monitor",  # "monitor" | "story"
        owner_key: str = "",
        user_id: str | None = None,
    ):
        self.session_id = session_id
        self.session_secret = session_secret
        self.delete_token = delete_token
        self.mode = mode
        self.owner_key = owner_key
        self.user_id = user_id
        self.state = self._new_state()
        self.choices_made: list[dict] = []  # [{choice_id, option_key, timestamp}, ...]
        self.current_route: str | None = None  # 检测到的当前路线
        self.game_path: str | None = None  # 本地游戏路径（local 模式）
        self.game_info: dict | None = None  # 游戏路径校验信息
        self.local_visual_assets: dict[str, list[str]] = {"backgrounds": [], "characters": [], "all": []}
        self.local_asset_registry: dict[str, str] = {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def _new_state(self) -> SessionState:
        return SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
            module_scores=make_zero_module_vector(0.0),
            module_counts={key: 0 for key in MODULE_KEYS},
            dimension_counts={key: 0 for key in CORE_DIMENSION_KEYS},
        )


class SenrenMonitorService:
    """千恋万花监视器服务"""

    def __init__(self):
        self._sessions: dict[str, SenrenMonitorSession] = {}
        self._scoring_engine = ScoringEngine()

    # ============================================================
    # Local visual assets
    # ============================================================

    def attach_local_visual_assets(self, session: SenrenMonitorSession, game_path: str) -> dict[str, list[str]]:
        assets = self.discover_local_visual_assets(game_path)
        session.local_visual_assets = assets
        return assets

    def discover_local_visual_assets(self, game_path: str) -> dict[str, list[str]]:
        root = Path(game_path)
        if not root.exists() or not root.is_dir():
            return {"backgrounds": [], "characters": [], "all": []}

        backgrounds: list[str] = []
        characters: list[str] = []
        all_images: list[str] = []
        scanned = 0
        for item in root.rglob("*"):
            if scanned >= LOCAL_ASSET_SCAN_LIMIT:
                break
            scanned += 1
            if not item.is_file() or item.suffix.lower() not in LOCAL_IMAGE_SUFFIXES:
                continue
            try:
                rel = item.relative_to(root)
            except ValueError:
                continue
            if {part.lower() for part in rel.parts} & LOCAL_ASSET_SKIP_PARTS:
                continue

            lowered = rel.as_posix().lower()
            resolved = str(item.resolve())
            all_images.append(resolved)
            if any(keyword in lowered for keyword in LOCAL_CHARACTER_KEYWORDS):
                characters.append(resolved)
                continue
            if any(keyword in lowered for keyword in LOCAL_BACKGROUND_KEYWORDS):
                backgrounds.append(resolved)

        if not backgrounds:
            backgrounds = [
                image
                for image in all_images
                if not any(keyword in Path(image).as_posix().lower() for keyword in LOCAL_CHARACTER_KEYWORDS)
            ][:80]
        return {
            "backgrounds": backgrounds[:160],
            "characters": characters[:160],
            "all": all_images[:240],
        }

    def local_visual_asset_summary(self, game_path: str) -> dict:
        assets = self.discover_local_visual_assets(game_path)
        return {
            "local_game_images": len(assets.get("all", [])),
            "local_background_candidates": len(assets.get("backgrounds", [])),
            "local_character_candidates": len(assets.get("characters", [])),
        }

    def resolve_local_asset(self, session_id: str, asset_id: str) -> Path:
        session = self.get_session(session_id)
        raw_path = session.local_asset_registry.get(asset_id)
        if not raw_path:
            raise KeyError("local_asset_not_found")
        asset_path = Path(raw_path).resolve()
        roots = self._local_asset_roots(session)
        if not asset_path.is_file() or asset_path.suffix.lower() not in LOCAL_IMAGE_SUFFIXES:
            raise PermissionError("unsupported_local_asset")
        if not any(self._is_relative_to(asset_path, root) for root in roots):
            raise PermissionError("local_asset_outside_allowed_roots")
        return asset_path

    # ============================================================
    # 会话管理
    # ============================================================

    def start_session(self, mode: str = "monitor", owner_key: str = "", user_id: str | None = None) -> dict:
        """启动一次新的监视会话"""
        session_id = uuid4().hex[:12]
        session_secret = secrets.token_urlsafe(32)
        delete_token = secrets.token_urlsafe(24)

        session = SenrenMonitorSession(
            session_id=session_id,
            session_secret=session_secret,
            delete_token=delete_token,
            mode=mode,
            owner_key=owner_key,
            user_id=user_id,
        )
        self._sessions[session_id] = session

        return {
            "session_id": session_id,
            "session_secret": session_secret,
            "delete_token": delete_token,
            "state": session.state.model_dump(),
            "roadmap": self._build_roadmap(),
            "total_choices": len(get_all_mappings()),
        }

    def get_session(self, session_id: str) -> SenrenMonitorSession:
        if session_id not in self._sessions:
            raise KeyError(f"监视会话不存在: {session_id}")
        return self._sessions[session_id]

    def authorize(self, session_id: str, session_secret: str) -> SenrenMonitorSession:
        session = self.get_session(session_id)
        hashed = hashlib.sha256(session_secret.encode()).hexdigest()
        expected = hashlib.sha256(session.session_secret.encode()).hexdigest()
        if hashed != expected:
            raise PermissionError("会话密钥不匹配")
        return session

    # ============================================================
    # 选择提交与状态更新
    # ============================================================

    def submit_game_choice(
        self,
        session_id: str,
        choice_id: str,
        option_key: str,
    ) -> dict:
        """提交一个游戏选择，更新人格状态"""
        session = self.get_session(session_id)

        # 查找选择映射
        mapping = get_mapping(choice_id, option_key)
        if not mapping:
            raise ValueError(f"未找到选择映射: {choice_id}/{option_key}")

        # 查找游戏选择节点信息
        choice_node = CHOICE_BY_ID.get(choice_id)

        # 构造临时 ItemTemplate 用于评分引擎
        try:
            option = next(o for o in choice_node.options if o.key == option_key)
            option_text = option.text
        except (StopIteration, AttributeError):
            option_text = option_key

        item = ItemTemplate(
            id=f"{choice_id}_{option_key}",
            prompt=choice_node.context if choice_node else f"选择: {choice_id}",
            question_type="situational_choice",
            layer="core",
            dimension_weights=mapping.dimension_weights,
            subdimension_weights=mapping.subdimension_weights,
            module_affinities=mapping.module_affinities,
            discrimination=mapping.discrimination,
            difficulty=mapping.difficulty,
            scenario_tags=mapping.scenario_tags,
            options=[
                QuestionOption(key=option_key, text=option_text, score=1.0),
                QuestionOption(key="alternative", text="其他选项", score=0.0),
            ],
        )

        # 应用评分更新
        session.state = self._scoring_engine.apply_response(
            state=session.state,
            item=item,
            selected_option_key=option_key,
        )

        # 记录选择
        session.choices_made.append({
            "choice_id": choice_id,
            "option_key": option_key,
            "option_text": option_text,
            "context": choice_node.context if choice_node else "",
            "location": choice_node.location if choice_node else "",
            "characters": choice_node.characters if choice_node else [],
            "dimension_effects": mapping.dimension_weights,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # 检测路线
        session.current_route = self._detect_route(session.choices_made)
        session.updated_at = datetime.now(timezone.utc)

        return {
            "state": session.state.model_dump(),
            "choice_recorded": session.choices_made[-1],
            "total_choices_made": len(session.choices_made),
            "current_route": session.current_route,
            "can_generate_report": len(session.choices_made) >= getattr(settings, "senren_min_choices_for_report", 8),
            "remaining_until_report": max(getattr(settings, "senren_min_choices_for_report", 8) - len(session.choices_made), 0),
        }

    # ============================================================
    # 实时状态
    # ============================================================

    def get_live_state(self, session_id: str) -> dict:
        """获取当前实时人格状态"""
        session = self.get_session(session_id)

        # 计算角色契合度
        affinity = compute_character_affinity(session.state.core_mu)

        # 最高维度
        top_dims = sorted(
            session.state.core_mu.items(),
            key=lambda x: abs(x[1]),
            reverse=True,
        )[:3]

        return {
            "session_id": session_id,
            "mode": session.mode,
            "question_count": len(session.choices_made),
            "current_route": session.current_route,
            "core_mu": session.state.core_mu,
            "core_sigma": session.state.core_sigma,
            "top_dimensions": [
                {"key": k, "label": CORE_DIMENSION_LABELS.get(k, k), "score": v}
                for k, v in top_dims
            ],
            "character_affinity": affinity,
            "recent_choices": session.choices_made[-5:],
            "can_generate_report": len(session.choices_made) >= getattr(settings, "senren_min_choices_for_report", 8),
        }

    # ============================================================
    # 路线图
    # ============================================================

    def get_roadmap(self, session_id: str) -> dict:
        """获取选择路线图及已完成进度"""
        session = self.get_session(session_id)
        made_choice_ids = {c["choice_id"] for c in session.choices_made}

        nodes = []
        for choice in ALL_CHOICES:
            completed = choice.choice_id in made_choice_ids
            user_option = None
            if completed:
                for c in session.choices_made:
                    if c["choice_id"] == choice.choice_id:
                        user_option = c["option_key"]
                        break

            nodes.append({
                "choice_id": choice.choice_id,
                "chapter": choice.chapter,
                "location": choice.location,
                "characters": choice.characters,
                "context": choice.context,
                "prompt": choice.prompt,
                "options": [
                    {"key": o.key, "text": o.text, "affection_target": o.affection_target}
                    for o in choice.options
                ],
                "completed": completed,
                "user_option": user_option,
            })

        return {
            "nodes": nodes,
            "total": len(ALL_CHOICES),
            "completed": len(made_choice_ids),
            "current_route": session.current_route,
        }

    def get_vn_scene(self, session_id: str) -> dict:
        """Build the current playable visual-novel scene.

        The original game is not hooked here. This endpoint turns the next
        recorded Senren choice node plus local skills/personas into a playable
        web VN scene, optionally enriched by the configured DeepSeek-compatible
        AI provider.
        """
        session = self.get_session(session_id)
        made_choice_ids = {c["choice_id"] for c in session.choices_made}
        choice_node = next((choice for choice in ALL_CHOICES if choice.choice_id not in made_choice_ids), None)
        if choice_node is None:
            return {
                "completed": True,
                "session_id": session_id,
                "title": "尾声",
                "location": session.current_route or "织守镇",
                "mood": "afterglow",
                "speaker": "系统",
                "narrator_text": "所有关键选择已经记录完毕。",
                "character_text": "可以查看这次路线的报告，或者从头开始另一轮记录。",
                "choices": [],
                "ai_generated": False,
                "background_asset": self._background_asset_ref(
                    session,
                    None,
                    "/generated/galgame/background/old_school_building_hallway_sunset.png",
                    "ending hallway",
                ),
                "character_asset": None,
                "skill_enrichment": {},
                "asset_strategy": self._asset_strategy(session),
                "skill_driven": True,
            }

        fallback_scene = self._fallback_vn_scene(session, choice_node)
        ai_scene = self._try_ai_vn_scene(session, choice_node)
        if ai_scene:
            ai_speaker_identity = self._character_identity(str(ai_scene.get("speaker") or fallback_scene["speaker"]))
            ai_speaker = ai_speaker_identity["display_name"] or fallback_scene["speaker"]
            fallback_scene.update(
                {
                    "title": str(ai_scene.get("title") or fallback_scene["title"]),
                    "location": str(ai_scene.get("location") or fallback_scene["location"]),
                    "mood": str(ai_scene.get("mood") or fallback_scene["mood"]),
                    "speaker": ai_speaker,
                    "speaker_slug": ai_speaker_identity["slug"] or fallback_scene.get("speaker_slug", ""),
                    "speaker_source_name": ai_speaker_identity["source_name"] or fallback_scene.get("speaker_source_name", ""),
                    "narrator_text": str(ai_scene.get("narrator_text") or fallback_scene["narrator_text"]),
                    "character_text": str(ai_scene.get("character_text") or fallback_scene["character_text"]),
                    "ai_generated": True,
                    "skill_driven": True,
                }
            )
            if ai_speaker:
                fallback_scene["character_asset"] = self._character_asset_ref(
                    session,
                    ai_speaker,
                    self._character_fallback_url(ai_speaker_identity),
                    f"{ai_speaker} sprite",
                )
            choice_texts = ai_scene.get("choice_texts", {})
            if isinstance(choice_texts, dict):
                fallback_scene["choices"] = [
                    {
                        **choice,
                        "text": str(choice_texts.get(choice["option_key"]) or choice["text"]),
                    }
                    for choice in fallback_scene["choices"]
                ]
        return fallback_scene

    def _fallback_vn_scene(self, session: SenrenMonitorSession, choice_node: GameChoiceNode) -> dict:
        primary_identity = self._primary_speaker_identity(choice_node.characters)
        speaker = primary_identity["display_name"] or primary_identity["source_name"] or "将臣"
        speaker_slug = primary_identity["slug"]
        persona_enrichment = self._skill_enrichment(choice_node.characters)
        background_url = SENREN_BACKGROUND_ASSETS.get(
            choice_node.choice_id,
            "/generated/galgame/background/old_school_building_corridor.png",
        )
        character_url = self._character_fallback_url(primary_identity)
        character_identities = self._character_identities(choice_node.characters)

        return {
            "completed": False,
            "session_id": session.session_id,
            "choice_id": choice_node.choice_id,
            "chapter": choice_node.chapter,
            "title": self._scene_title(choice_node),
            "location": choice_node.location,
            "mood": self._scene_mood(choice_node),
            "speaker": speaker,
            "speaker_slug": speaker_slug,
            "speaker_source_name": primary_identity["source_name"],
            "narrator_text": choice_node.context,
            "character_text": choice_node.prompt,
            "characters": [item["display_name"] or item["source_name"] for item in character_identities],
            "source_characters": choice_node.characters,
            "character_identities": character_identities,
            "choices": [
                {
                    "option_key": option.key,
                    "text": option.text,
                    "affection_target": option.affection_target,
                }
                for option in choice_node.options
            ],
            "ai_generated": False,
            "skill_driven": bool(persona_enrichment),
            "asset_strategy": self._asset_strategy(session),
            "background_asset": self._background_asset_ref(
                session,
                choice_node,
                background_url,
                f"{choice_node.location} background",
            ),
            "character_asset": self._character_asset_ref(
                session,
                speaker,
                character_url,
                f"{speaker} sprite",
            ),
            "skill_enrichment": persona_enrichment,
            "recent_choices": session.choices_made[-6:],
            "current_route": session.current_route,
        }

    def _try_ai_vn_scene(self, session: SenrenMonitorSession, choice_node: GameChoiceNode) -> dict | None:
        persona_enrichment = self._skill_enrichment(choice_node.characters)
        character_identities = self._character_identities(choice_node.characters)
        primary_speaker = self._primary_speaker_identity(choice_node.characters)
        choices_payload = []
        for option in choice_node.options:
            mapping = get_mapping(choice_node.choice_id, option.key)
            choices_payload.append(
                {
                    "option_key": option.key,
                    "text": option.text,
                    "affection_target": option.affection_target,
                    "dimension_weights": mapping.dimension_weights if mapping else {},
                    "scenario_tags": mapping.scenario_tags if mapping else [],
                }
            )

        payload = {
            "mode": session.mode,
            "chapter": choice_node.chapter,
            "location": choice_node.location,
            "characters": [item["display_name"] or item["source_name"] for item in character_identities],
            "source_characters": choice_node.characters,
            "character_identities": character_identities,
            "primary_speaker": primary_speaker,
            "context": choice_node.context,
            "prompt": choice_node.prompt,
            "choices": choices_payload,
            "recent_choices": session.choices_made[-4:],
            "skill_personas": persona_enrichment,
            "skill_contract": {
                "enabled": True,
                "mode": "ai_first_every_scene",
                "rules": [
                    "Use current speaker's skill persona as the primary voice source.",
                    "Keep tone, speaking pace, emotional tells, priorities, boundaries, and sample voice consistent.",
                    "Do not mention personality measurement, scoring, dimensions, options, or backend analysis.",
                    "Generate natural visual-novel dialogue that could be played directly.",
                    "choice_texts must be in-world actions or lines, not psychometric labels.",
                ],
            },
            "style": {
                "format": "single-screen visual novel",
                "reference": "paper2galgame style: sprite, dialogue box, log/hide/auto controls",
                "tone": "natural galgame dialogue, not questionnaire language",
                "no_measurement_terms": True,
            },
            "private_analysis_seed": {
                "current_route": session.current_route,
                "core_mu": session.state.core_mu,
            },
        }
        return ai_service.generate_galgame_scene(payload)

    def _background_asset_ref(
        self,
        session: SenrenMonitorSession,
        choice_node: GameChoiceNode | None,
        fallback_url: str,
        alt: str,
    ) -> dict:
        local_path = self._select_local_background(session, choice_node)
        if local_path:
            return {
                "url": self._register_local_asset(session, "background", local_path),
                "alt": alt,
                "source": "local_game",
            }
        return {"url": fallback_url, "alt": alt, "source": "generated_fallback"}

    def _character_asset_ref(
        self,
        session: SenrenMonitorSession,
        character_name: str,
        fallback_url: str | None,
        alt: str,
    ) -> dict | None:
        local_path = self._select_local_character(session, character_name)
        if local_path:
            return {
                "url": self._register_local_asset(session, "character", local_path),
                "alt": alt,
                "source": "local_or_generated_character",
            }
        if fallback_url:
            return {"url": fallback_url, "alt": alt, "source": "generated_fallback"}
        return None

    def _select_local_background(self, session: SenrenMonitorSession, choice_node: GameChoiceNode | None) -> str | None:
        backgrounds = session.local_visual_assets.get("backgrounds", [])
        if not backgrounds:
            return None
        if not choice_node:
            return backgrounds[0]
        target = " ".join([choice_node.choice_id, choice_node.location, choice_node.chapter]).lower()
        ranked = sorted(
            backgrounds,
            key=lambda path: self._asset_match_score(Path(path).as_posix().lower(), target),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _select_local_character(self, session: SenrenMonitorSession, character_name: str) -> str | None:
        if not character_name:
            return None
        character_dir_match = self._match_character_asset_dir(character_name)
        if character_dir_match:
            return character_dir_match
        characters = session.local_visual_assets.get("characters", [])
        if not characters:
            return None
        aliases = self._character_aliases(character_name)
        ranked = sorted(
            characters,
            key=lambda path: max(self._asset_match_score(Path(path).as_posix().lower(), alias) for alias in aliases),
            reverse=True,
        )
        if ranked and max(self._asset_match_score(Path(ranked[0]).as_posix().lower(), alias) for alias in aliases) > 0:
            return ranked[0]
        return ranked[0] if len(characters) == 1 else None

    def _match_character_asset_dir(self, character_name: str) -> str | None:
        roots = [root for root in self._character_asset_roots() if root.exists()]
        if not roots:
            return None
        aliases = self._character_aliases(character_name)
        images = [
            item
            for root in roots
            for item in root.rglob("*")
            if item.is_file() and item.suffix.lower() in LOCAL_IMAGE_SUFFIXES
        ]
        ranked = sorted(
            images,
            key=lambda path: max(self._asset_match_score(path.as_posix().lower(), alias) for alias in aliases),
            reverse=True,
        )
        if ranked and max(self._asset_match_score(ranked[0].as_posix().lower(), alias) for alias in aliases) > 0:
            return str(ranked[0].resolve())
        return None

    def _register_local_asset(self, session: SenrenMonitorSession, kind: str, raw_path: str) -> str:
        digest = hashlib.sha256(f"{session.session_secret}:{raw_path}".encode("utf-8")).hexdigest()[:16]
        asset_id = f"{kind}-{digest}"
        session.local_asset_registry[asset_id] = raw_path
        return f"/api/senren/monitor/{session.session_id}/asset/{asset_id}"

    def _character_asset_root(self) -> Path:
        root = Path(settings.senren_character_asset_dir)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[3] / root
        return root.resolve()

    def _generated_character_root(self) -> Path:
        root = Path(settings.galgame_asset_public_dir)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[3] / root
        return (root / "character").resolve()

    def _character_asset_roots(self) -> list[Path]:
        return [self._character_asset_root(), self._generated_character_root()]

    def _local_asset_roots(self, session: SenrenMonitorSession) -> list[Path]:
        roots = self._character_asset_roots()
        if session.game_path:
            roots.append(Path(session.game_path).resolve())
        return roots

    def _asset_strategy(self, session: SenrenMonitorSession) -> str:
        if session.local_visual_assets.get("all"):
            return "local_game_assets_first"
        if any(root.exists() for root in self._character_asset_roots()):
            return "local_character_assets_first"
        return "generated_fallback"

    def _character_identity(self, character_name: str) -> dict[str, str]:
        try:
            from app.domain.senren_skills_loader import resolve_character_identity

            return resolve_character_identity(character_name)
        except Exception:
            name = (character_name or "").strip()
            return {"source_name": name, "slug": "", "display_name": name}

    def _character_identities(self, characters: list[str]) -> list[dict[str, str]]:
        identities = [self._character_identity(name) for name in characters]
        return [identity for identity in identities if identity["source_name"] or identity["display_name"]]

    def _primary_speaker_identity(self, characters: list[str]) -> dict[str, str]:
        identities = self._character_identities(characters)
        for identity in identities:
            if identity["slug"] != "masamichi":
                return identity
        if identities:
            return identities[0]
        return self._character_identity("将臣")

    def _character_fallback_url(self, identity: dict[str, str]) -> str | None:
        for key in (identity.get("display_name", ""), identity.get("source_name", "")):
            if key and key in SENREN_CHARACTER_ASSETS:
                return SENREN_CHARACTER_ASSETS[key]
        return None

    def _character_aliases(self, character_name: str) -> list[str]:
        identity = self._character_identity(character_name)
        aliases = {
            character_name.lower(),
            identity.get("slug", "").lower(),
            identity.get("display_name", "").lower(),
            identity.get("source_name", "").lower(),
        }
        return [alias for alias in aliases if alias]

    def _asset_match_score(self, path_text: str, target_text: str) -> int:
        score = 0
        for token in target_text.replace("-", " ").replace("_", " ").split():
            if token and token in path_text:
                score += 2
        if target_text and target_text in path_text:
            score += 5
        return score

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _skill_enrichment(self, characters: list[str]) -> dict:
        try:
            from app.domain.senren_skills_loader import get_storymode_character_enrichment

            return get_storymode_character_enrichment(characters)
        except Exception:
            return {}

    def _scene_title(self, choice_node: GameChoiceNode) -> str:
        chapter = choice_node.chapter.split("-")[-1] if "-" in choice_node.chapter else choice_node.chapter
        if choice_node.location:
            return f"{chapter} · {choice_node.location}"
        return chapter

    def _scene_mood(self, choice_node: GameChoiceNode) -> str:
        tags = []
        for option in choice_node.options:
            mapping = get_mapping(choice_node.choice_id, option.key)
            if mapping:
                tags.extend(mapping.scenario_tags[:2])
        return " / ".join(dict.fromkeys(tags).keys()) or "静かな分岐"

    def _build_roadmap(self) -> dict:
        """构建完整路线图（无会话上下文）"""
        nodes = []
        for choice in ALL_CHOICES:
            nodes.append({
                "choice_id": choice.choice_id,
                "chapter": choice.chapter,
                "location": choice.location,
                "characters": choice.characters,
                "context": choice.context,
                "prompt": choice.prompt,
                "options": [
                    {"key": o.key, "text": o.text, "affection_target": o.affection_target}
                    for o in choice.options
                ],
            })
        return {"nodes": nodes, "total": len(ALL_CHOICES)}

    # ============================================================
    # 路线检测
    # ============================================================

    def _detect_route(self, choices_made: list[dict]) -> str | None:
        """根据已做选择检测当前最可能的路线"""
        if not choices_made:
            return None

        # 简单启发式：统计各角色好感度相关选择
        affection = {}
        for c in choices_made:
            choice_node = CHOICE_BY_ID.get(c["choice_id"])
            if choice_node:
                for opt in choice_node.options:
                    if opt.key == c["option_key"] and opt.affection_target != "none":
                        affection[opt.affection_target] = affection.get(opt.affection_target, 0) + 1

        if not affection:
            return "共通线"

        # 返回好感度最高的角色
        top_char = max(affection, key=affection.get)
        route_map = {
            "芳乃": "芳乃线",
            "丛雨": "丛雨线",
            "茉子": "茉子线",
            "蕾娜": "蕾娜线",
            "小春": "小春线",
            "芦花": "芦花线",
        }
        return route_map.get(top_char, f"{top_char}线")

    # ============================================================
    # 报告生成
    # ============================================================

    def generate_report(
        self,
        session_id: str,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> dict:
        """生成千恋万花主题人格报告"""
        session = self.get_session(session_id)

        if len(session.choices_made) < getattr(settings, "senren_min_choices_for_report", 8):
            raise ValueError(f"至少需要{getattr(settings, 'senren_min_choices_for_report', 8)}个选择才能生成报告")

        # 复用标准报告生成逻辑
        top_dimensions = sorted(
            session.state.core_mu.items(),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:3]
        structural_labels = [
            StructuralLabel(
                dimension=dim,
                label=CORE_DIMENSION_LABELS.get(dim, dim),
                score=score,
            )
            for dim, score in top_dimensions
        ]

        cluster_mix = clustering_service.cluster_memberships_for_state(session.state)
        cluster_name = cluster_mix[0].cluster_name
        cluster_label = cluster_mix[0].narrative_label

        # 应用游戏主题叙事标签覆盖
        narrative_label = SENREN_NARRATIVE_LABELS.get(cluster_name, cluster_label)
        narrative_label = render_narrative_label(session.state, narrative_label)

        # 角色契合度
        affinity = compute_character_affinity(session.state.core_mu)
        best_match = max(affinity, key=affinity.get) if affinity else "未知"

        # 核心维度百分比
        score_clip = settings.score_clip
        core_bars = {
            CORE_DIMENSION_LABELS[key]: round(((max(-score_clip, min(score_clip, score)) + score_clip) / (2 * score_clip)) * 100, 1)
            for key, score in session.state.core_mu.items()
        }

        # 选择概要
        choice_summary = []
        for c in session.choices_made:
            choice_summary.append({
                "choice_id": c["choice_id"],
                "context": c.get("context", ""),
                "option_text": c.get("option_text", ""),
                "location": c.get("location", ""),
                "characters": c.get("characters", []),
            })

        # 不确定性摘要
        uncertainty_summary = {
            "avg_sigma": sum(session.state.core_sigma.values()) / len(session.state.core_sigma),
            "stable_dimensions": sum(1 for sigma in session.state.core_sigma.values() if sigma <= 1.0),
            "most_uncertain": max(session.state.core_sigma.items(), key=lambda x: x[1])[0],
        }

        # 路线分析
        route_analysis = None
        if session.current_route and session.current_route in ALL_ROUTES:
            route = ALL_ROUTES[session.current_route]
            route_analysis = {
                "route_name": route["route_name"],
                "description": route["description"],
                "key_traits": route.get("key_personality_traits", {}),
            }

        report_data = {
            "session_id": session_id,
            "question_count": len(session.choices_made),
            "current_route": session.current_route,
            "route_analysis": route_analysis,
            "cluster_name": cluster_name,
            "narrative_label": narrative_label,
            "cluster_confidence": cluster_mix[0].weight,
            "cluster_mix": [m.model_dump() for m in cluster_mix],
            "structural_labels": [l.model_dump() for l in structural_labels],
            "core_bars": core_bars,
            "character_affinity": affinity,
            "best_match_character": best_match,
            "uncertainty_summary": uncertainty_summary,
            "choice_summary": choice_summary,
        }

        # 尝试 AI 解读
        try:
            ai_payload = {
                "question_count": len(session.choices_made),
                "cluster_name": cluster_name,
                "narrative_label": narrative_label,
                "cluster_confidence": cluster_mix[0].weight,
                "structural_labels": [l.model_dump() for l in structural_labels],
                "core_bars": core_bars,
                "uncertainty_summary": uncertainty_summary,
                "current_route": session.current_route,
                "best_match_character": best_match,
            }
            ai_result = ai_service.interpret_report_with_config(ai_payload, runtime_ai_config)
            report_data["ai_summary"] = str(ai_result.get("ai_summary", ""))
            report_data["ai_aliases"] = [str(a) for a in ai_result.get("ai_aliases", [])]
        except Exception:
            report_data["ai_summary"] = ""
            report_data["ai_aliases"] = []

        return report_data

    # ============================================================
    # 扩展场景获取（模式 B：独立故事模式）
    # ============================================================

    def get_next_scenario(self, session_id: str) -> dict | None:
        """获取下一个扩展场景（用于独立故事模式）"""
        session = self.get_session(session_id)
        made_ids = {c["choice_id"] for c in session.choices_made}

        for mapping in EXPANDED_SCENARIOS:
            if mapping.choice_id not in made_ids:
                # 构造场景描述
                choice_node = CHOICE_BY_ID.get(mapping.choice_id)
                context = choice_node.context if choice_node else "在穗织镇的冒险中，你面临一个选择..."

                return {
                    "choice_id": mapping.choice_id,
                    "context": context,
                    "option_key": mapping.option_key,
                    "discrimination": mapping.discrimination,
                    "difficulty": mapping.difficulty,
                }

        return None

    # ============================================================
    # 会话列表与清理
    # ============================================================

    def list_sessions(self) -> list[dict]:
        result = []
        for sid, session in self._sessions.items():
            result.append({
                "session_id": sid,
                "mode": session.mode,
                "current_route": session.current_route,
                "choices_count": len(session.choices_made),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            })
        return sorted(result, key=lambda s: s["updated_at"], reverse=True)

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False


# 全局单例
senren_monitor_service = SenrenMonitorService()
