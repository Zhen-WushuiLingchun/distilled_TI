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
