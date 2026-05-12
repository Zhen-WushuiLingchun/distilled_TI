"""In-memory session service for the MVP."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from app.core.config import settings
from app.domain.dimensions import (
    AI_PROBE_DIMENSIONS_BY_KEY,
    AI_PROBE_DIMENSION_KEYS,
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
from app.domain.item_bank import LIKERT_OPTIONS, build_seed_item_bank
from app.domain.models import (
    ClusterOverview,
    ItemInstance,
    ItemTemplate,
    ItemTemplateCreate,
    QuestionOption,
    RewritePreviewBundle,
    SessionAccessGrant,
    SessionHistoryEntry,
    SessionRecord,
    SessionReport,
    SessionState,
    SessionSummary,
    VectorSearchHit,
    WorkbenchCheckpoint,
    WorkbenchEvidence,
    WorkbenchEvidenceItem,
    WorkbenchMilestone,
    WorkbenchSignal,
)
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.clustering import clustering_service
from app.services.generation import generation_service
from app.services.scoring import ScoringEngine
from app.services.storage import local_session_store
from app.services.validators import validate_item_template
from app.services.vector_indexer import vector_indexer


class SessionService:
    def __init__(self) -> None:
        self._items: dict[str, ItemTemplate] = {item.id: item for item in build_seed_item_bank()}
        self._items.update({item.id: item for item in local_session_store.load_templates()})
        self._sessions: dict[str, SessionRecord] = {}
        self._instances: dict[str, ItemInstance] = {}
        self._scoring_engine = ScoringEngine()

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

    def cleanup_expired(self) -> int:
        return local_session_store.cleanup_expired()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _mint_access_grant(self) -> SessionAccessGrant:
        return SessionAccessGrant(
            session_id="",
            session_secret=secrets.token_urlsafe(32),
            delete_token=secrets.token_urlsafe(32),
        )

    def _bind_access_grant(
        self,
        record: SessionRecord,
        grant: SessionAccessGrant,
        owner_key: str | None,
    ) -> SessionAccessGrant:
        record.session_secret_hash = self._hash_token(grant.session_secret)
        record.delete_token_hash = self._hash_token(grant.delete_token)
        record.owner_key = owner_key
        record.updated_at = datetime.now(UTC)
        local_session_store.save_session(record)
        self._sessions[record.session_id] = record
        return grant.model_copy(update={"session_id": record.session_id})

    def issue_session_access(self, session_id: str, owner_key: str | None = None) -> SessionAccessGrant:
        record = self.get_session(session_id, force_reload=True)
        grant = self._mint_access_grant()
        return self._bind_access_grant(record, grant, owner_key)

    def _verify_owner(self, record: SessionRecord, owner_key: str | None) -> None:
        if record.owner_key and not owner_key:
            raise PermissionError("session_owner_required")
        if record.owner_key and owner_key and not secrets.compare_digest(record.owner_key, owner_key):
            raise PermissionError("session_owner_mismatch")

    def authorize_session(self, session_id: str, session_secret: str, owner_key: str | None = None) -> SessionRecord:
        record = self.get_session(session_id, force_reload=True)
        if not record.session_secret_hash:
            raise PermissionError("session_secret_required")
        if not secrets.compare_digest(record.session_secret_hash, self._hash_token(session_secret)):
            raise PermissionError("invalid_session_secret")
        self._verify_owner(record, owner_key)
        return record

    def authorize_session_delete(self, session_id: str, delete_token: str, owner_key: str | None = None) -> SessionRecord:
        record = self.get_session(session_id, force_reload=True)
        if not record.delete_token_hash:
            raise PermissionError("delete_token_required")
        if not secrets.compare_digest(record.delete_token_hash, self._hash_token(delete_token)):
            raise PermissionError("invalid_delete_token")
        self._verify_owner(record, owner_key)
        return record

    def start_session(
        self,
        mode: str = "core",
        runtime_ai_config: AIProviderConfig | None = None,
        owner_key: str | None = None,
        user_id: str | None = None,
    ) -> tuple[SessionRecord, ItemInstance, SessionAccessGrant]:
        self.cleanup_expired()
        session_id = str(uuid4())
        record = SessionRecord(session_id=session_id, mode=mode, state=self._new_state(), user_id=user_id)
        next_item = self._generate_next_instance(record, runtime_ai_config)
        record.current_item_id = next_item.id
        record.current_template_id = next_item.template_id
        grant = self._bind_access_grant(record, self._mint_access_grant(), owner_key)
        return record, next_item, grant

    def get_session(self, session_id: str, force_reload: bool = False) -> SessionRecord:
        self.cleanup_expired()
        if not force_reload and session_id in self._sessions:
            return self._sessions[session_id]
        record = local_session_store.load_session(session_id)
        if record is None:
            raise KeyError("session_not_found")
        self._sessions[session_id] = record
        return record

    def get_item(self, item_id: str) -> ItemInstance:
        if item_id in self._instances:
            return self._instances[item_id]
        instance = local_session_store.load_item_instance(item_id)
        if instance is None:
            raise KeyError("item_instance_not_found")
        self._instances[item_id] = instance
        return instance

    def list_items(self, include_archived: bool = False) -> list[ItemTemplate]:
        items = self._items.values()
        if not include_archived:
            items = [item for item in items if not item.archived]
        return sorted(items, key=lambda item: item.id)

    def list_item_instances(self, session_id: str | None = None) -> list[ItemInstance]:
        return local_session_store.list_item_instances(session_id)

    def list_sessions(self, user_id: str | None = None) -> list[SessionHistoryEntry]:
        histories = local_session_store.list_sessions(user_id=user_id)
        for entry in histories:
            try:
                record = self.get_session(entry.session_id)
                cluster_name, narrative_label, _confidence = clustering_service.cluster_for_state(record.state)
                entry.cluster_name = cluster_name
                entry.narrative_label = narrative_label
            except KeyError:
                continue
        return histories

    def add_item(self, payload: ItemTemplateCreate) -> ItemTemplate:
        errors = validate_item_template(payload)
        if errors:
            raise ValueError("；".join(errors))
        item = ItemTemplate(
            id=f"user-{uuid4()}",
            prompt=payload.prompt,
            question_type=payload.question_type,
            layer=payload.layer,
            dimension_weights=payload.dimension_weights,
            subdimension_weights=payload.subdimension_weights,
            module_affinities=payload.module_affinities,
            discrimination=max(payload.discrimination, 1.15),
            difficulty=payload.difficulty,
            scenario_tags=payload.scenario_tags,
            is_anchor=payload.is_anchor,
            allow_rewrite=payload.allow_rewrite,
            options=payload.options,
        )
        self._items[item.id] = item
        local_session_store.save_template(item)
        vector_indexer.index_template(item)
        return item

    def update_item(self, template_id: str, payload: ItemTemplateCreate) -> ItemTemplate:
        if template_id not in self._items:
            raise KeyError("template_not_found")
        errors = validate_item_template(payload)
        if errors:
            raise ValueError("；".join(errors))
        existing = self._items[template_id]
        updated = existing.model_copy(
            update={
                "prompt": payload.prompt,
                "question_type": payload.question_type,
                "layer": payload.layer,
                "dimension_weights": payload.dimension_weights,
                "subdimension_weights": payload.subdimension_weights,
                "module_affinities": payload.module_affinities,
                "discrimination": max(payload.discrimination, 1.15),
                "difficulty": payload.difficulty,
                "scenario_tags": payload.scenario_tags,
                "is_anchor": payload.is_anchor,
                "allow_rewrite": payload.allow_rewrite,
                "options": payload.options,
            }
        )
        self._items[template_id] = updated
        local_session_store.save_template(updated)
        vector_indexer.index_template(updated)
        return updated

    def preview_rewrite(
        self,
        session_id: str,
        template_id: str,
        style_hint: str | None = None,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> RewritePreviewBundle:
        session = self.get_session(session_id)
        template = self._items[template_id]
        if template.archived:
            raise KeyError("template_archived")
        actual_style_hint = style_hint or generation_service.recommended_style_hint(session)
        return generation_service.preview_rewrite(session, template, actual_style_hint, runtime_ai_config)

    def select_next_question(
        self,
        session: SessionRecord,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> ItemTemplate:
        active_ai_config = runtime_ai_config or ai_service.get_config()
        if session.state.question_count >= settings.max_questions_per_session:
            raise ValueError("item_bank_exhausted")

        coverage_counts = {key: 0 for key in CORE_DIMENSION_KEYS}
        for answer in session.state.answers:
            instance = self.get_item(answer.item_id)
            for dimension in instance.dimension_weights:
                coverage_counts[dimension] += 1

        recent_template_ids = self._recent_template_ids(session)
        recent_prompts = generation_service.recent_session_prompts(session, self._prompt_for_item, settings.semantic_repeat_window)
        recent_scenarios = self._recent_scenario_tags(session, settings.scenario_repeat_window)
        live_templates = self._live_templates_for_session(session)
        seen_template_ids = {
            answer.template_id
            for answer in session.state.answers
            if not answer.template_id.startswith("probe-")
        }
        candidate_templates = [item for item in live_templates if item.id not in seen_template_ids] or live_templates
        recent_modes = self._recent_generation_modes(session, 12)
        recent_answer_count = max(len(recent_modes), 1)
        recent_llm_ratio = recent_modes.count("llm_rewrite") / recent_answer_count

        def need_score(item: ItemTemplate) -> float:
            uncertainty_gain = sum(
                session.state.core_sigma[dimension] * abs(weight) for dimension, weight in item.dimension_weights.items()
            )
            coverage_penalty = sum(coverage_counts[dimension] for dimension in item.dimension_weights) * 0.12
            novelty_bonus = 0.15 if len(set(item.scenario_tags)) > 1 else 0.05
            recency_penalty = 6.0 if item.id in recent_template_ids else 0.0
            semantic_similarity = generation_service.max_prompt_similarity(item.prompt, recent_prompts)
            semantic_penalty = 2.2 if semantic_similarity >= settings.semantic_repeat_threshold else semantic_similarity * 0.9
            scenario_penalty = 0.0
            if recent_scenarios and item.scenario_tags:
                overlap = len(set(item.scenario_tags) & recent_scenarios) / max(len(set(item.scenario_tags)), 1)
                scenario_penalty = overlap * 0.55
            phase_bonus = 0.2 * item.discrimination
            if active_ai_config is not None and item.allow_rewrite:
                rewrite_gap = max(0.0, settings.ai_rewrite_target_ratio - recent_llm_ratio)
                phase_bonus += settings.ai_rewrite_priority_bonus * (0.45 + rewrite_gap)
            if session.state.question_count < settings.min_questions_for_report:
                if item.layer == "core":
                    phase_bonus += 0.3
                if item.is_anchor:
                    phase_bonus += 0.18
                if item.layer == "sub":
                    ready_subs = [
                        key
                        for key in item.subdimension_weights
                        if session.state.dimension_counts.get(SUBDIMENSION_TO_PARENT[key], 0) >= settings.subdimension_unlock_threshold
                    ]
                    if ready_subs and session.state.question_count >= max(settings.min_questions_for_report - 8, 8):
                        phase_bonus += 0.7
                    if ready_subs and not session.state.unlocked_subdimensions:
                        phase_bonus += 0.55
                if item.layer == "module" and session.state.question_count >= max(settings.min_questions_for_report - 5, 12):
                    phase_bonus += 0.45
            else:
                if item.layer == "sub":
                    phase_bonus += 0.25
                    if not session.state.unlocked_subdimensions:
                        phase_bonus += 0.45
                if item.layer == "module":
                    phase_bonus += 0.18
            return uncertainty_gain + novelty_bonus + phase_bonus - coverage_penalty - recency_penalty - semantic_penalty - scenario_penalty

        ranked_templates = sorted(candidate_templates, key=need_score, reverse=True)
        return generation_service.choose_template(session, ranked_templates[: settings.ranked_candidate_window])

    def _generate_next_instance(
        self,
        session: SessionRecord,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> ItemInstance:
        active_ai_config = runtime_ai_config or ai_service.get_config()
        if self._should_generate_probe(session, active_ai_config):
            probe_instance = self._generate_probe_instance(session, active_ai_config)
            if probe_instance is not None:
                self._instances[probe_instance.id] = probe_instance
                local_session_store.save_item_instance(probe_instance)
                vector_indexer.index_item_instance(probe_instance)
                session.current_item_id = probe_instance.id
                session.current_template_id = probe_instance.template_id
                session.updated_at = datetime.now(UTC)
                return probe_instance

        template = self.select_next_question(session, active_ai_config)
        style_hint = generation_service.recommended_style_hint(session)
        instance, _preview = generation_service.materialize_instance(session, template, style_hint, active_ai_config)
        self._instances[instance.id] = instance
        local_session_store.save_item_instance(instance)
        vector_indexer.index_item_instance(instance)
        session.current_item_id = instance.id
        session.current_template_id = template.id
        session.updated_at = datetime.now(UTC)
        return instance

    def _should_generate_probe(self, session: SessionRecord, runtime_ai_config: AIProviderConfig | None = None) -> bool:
        active_ai_config = runtime_ai_config or ai_service.get_config()
        first_question = settings.ai_probe_first_question if active_ai_config is not None else 6
        if session.state.question_count < first_question:
            return False
        if session.state.question_count >= settings.max_questions_per_session:
            return False
        probe_count = sum(
            session.state.sub_counts.get(key, 0)
            for key in AI_PROBE_DIMENSION_KEYS
        )
        max_probe_count = settings.ai_probe_max_count if active_ai_config is not None else 4
        if probe_count >= max_probe_count:
            return False
        if active_ai_config is not None:
            if session.state.question_count < 10 and probe_count >= 1:
                return False
            if session.state.question_count < 20 and probe_count >= 3:
                return False
        else:
            if session.state.question_count < 12 and probe_count >= 1:
                return False
            if 12 <= session.state.question_count < settings.min_questions_for_report and probe_count >= 2:
                return False
        if self._recent_probe_ratio(session, 12) < settings.ai_probe_target_ratio and active_ai_config is not None:
            recent_window = 2
        else:
            recent_window = 4
        recent_probe = any(
            answer.template_id.startswith("probe-")
            for answer in session.state.answers[-recent_window:]
        )
        return not recent_probe

    def _generate_probe_instance(
        self,
        session: SessionRecord,
        runtime_ai_config: AIProviderConfig | None,
    ) -> ItemInstance | None:
        active_ai_config = runtime_ai_config or ai_service.get_config()
        candidates = self._probe_candidates(session)[:3]
        if not candidates:
            return None
        selected = ai_service.generate_probe_question(
            session_snapshot=self._probe_session_digest(session),
            probe_candidates=[
                {
                    "key": definition.key,
                    "label": definition.label,
                    "parent": definition.parent,
                    "description": definition.description,
                    "safe_domain": definition.safe_domain,
                    "fallback_prompt": definition.fallback_prompts[0],
                    "contrast_left": definition.contrast_pairs[0][0],
                    "contrast_right": definition.contrast_pairs[0][1],
                }
                for definition in candidates
            ],
            runtime_config=active_ai_config,
            preferred_mode=self._preferred_probe_mode(session, active_ai_config),
        )
        definition = AI_PROBE_DIMENSIONS_BY_KEY.get(str(selected.get("probe_key", "")), candidates[0])
        prompt = str(selected.get("prompt", definition.fallback_prompts[0])).strip()
        scenario_tags = [definition.safe_domain, "ai_probe", *[str(tag) for tag in selected.get("scenario_tags", [])][:2]]
        probe_mode = str(selected.get("probe_mode", "statement"))
        question_type = "likert_5"
        options = LIKERT_OPTIONS
        if probe_mode == "contrast":
            question_type = "contrast_5"
            left_anchor = str(selected.get("left_anchor", "")).strip()
            right_anchor = str(selected.get("right_anchor", "")).strip()
            if not left_anchor or not right_anchor:
                left_anchor, right_anchor = definition.contrast_pairs[0]
            options = self._contrast_options(left_anchor, right_anchor)

        return ItemInstance(
            id=f"inst-{uuid4()}",
            template_id=f"probe-{definition.key}",
            session_id=session.session_id,
            prompt=prompt,
            question_type=question_type,
            layer="probe",
            dimension_weights={definition.parent: 0.45},
            subdimension_weights={definition.key: 1.0},
            module_affinities={},
            discrimination=1.28,
            difficulty=0.15,
            scenario_tags=scenario_tags[:4],
            is_anchor=False,
            allow_rewrite=False,
            options=options,
            generation_mode="probe",
            validator_passed=True,
        )

    def _probe_candidates(self, session: SessionRecord):
        eligible = []
        recent_template_ids = self._recent_template_ids(session)
        for key in AI_PROBE_DIMENSION_KEYS:
            definition = AI_PROBE_DIMENSIONS_BY_KEY[key]
            if f"probe-{key}" in recent_template_ids:
                continue
            if session.state.dimension_counts.get(definition.parent, 0) < max(settings.subdimension_unlock_threshold - 1, 2):
                continue
            sigma = session.state.sub_sigma.get(key, settings.default_sigma)
            count = session.state.sub_counts.get(key, 0)
            score = sigma + max(0.0, 0.35 - count * 0.12)
            eligible.append((score, definition))
        eligible.sort(key=lambda item: item[0], reverse=True)
        return [definition for _score, definition in eligible]

    def _probe_session_digest(self, session: SessionRecord) -> dict[str, object]:
        top_core = sorted(
            session.state.core_mu.items(),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:3]
        top_uncertainty = sorted(
            session.state.core_sigma.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:2]
        emerging_subs = sorted(
            (
                (key, session.state.sub_counts.get(key, 0))
                for key in session.state.sub_counts
                if session.state.sub_counts.get(key, 0) > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        return {
            "question_count": session.state.question_count,
            "top_core_signals": [
                {"label": CORE_DIMENSION_LABELS.get(key, key), "score": round(score, 3)}
                for key, score in top_core
            ],
            "highest_uncertainty_core": [
                {"dimension": key, "sigma": round(sigma, 3)}
                for key, sigma in top_uncertainty
            ],
            "emerging_subdimensions": [
                {"label": SUBDIMENSION_LABELS.get(key, key), "sample_count": count}
                for key, count in emerging_subs
            ],
            "active_modules": [MODULE_LABELS.get(key, key) for key in session.state.active_modules[:3]],
        }

    def _contrast_options(self, left_anchor: str, right_anchor: str):
        return [
            QuestionOption(key="strongly_left", text=f"明显更接近：{left_anchor}", score=-1.0),
            QuestionOption(key="left", text=f"稍偏向：{left_anchor}", score=-0.5),
            QuestionOption(key="neutral", text="两边都能理解 / 看情况", score=0.0),
            QuestionOption(key="right", text=f"稍偏向：{right_anchor}", score=0.5),
            QuestionOption(key="strongly_right", text=f"明显更接近：{right_anchor}", score=1.0),
        ]

    def get_next_question(
        self,
        session_id: str,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> ItemInstance:
        session = self.get_session(session_id)
        next_item = self._generate_next_instance(session, runtime_ai_config)
        local_session_store.save_session(session)
        return next_item

    def submit_answer(
        self,
        session_id: str,
        item_id: str,
        option_key: str,
        latency_ms: int | None = None,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> tuple[SessionRecord, ItemInstance | None]:
        session = self.get_session(session_id)
        item = self.get_item(item_id)
        session.state = self._scoring_engine.apply_response(session.state, item, option_key, latency_ms)
        session.updated_at = datetime.now(UTC)
        next_item: ItemInstance | None = None
        if session.state.question_count < settings.max_questions_per_session:
            next_item = self._generate_next_instance(session, runtime_ai_config)
        else:
            session.current_item_id = None
            session.current_template_id = None
        local_session_store.save_session(session)
        vector_indexer.index_session_snapshot(session)
        return session, next_item

    def build_report(
        self,
        session_id: str,
        runtime_ai_config: AIProviderConfig | None = None,
        naming_style: str | None = None,
    ) -> SessionReport:
        session = self.get_session(session_id)
        if session.state.question_count < settings.min_questions_for_report:
            raise ValueError("report_not_ready")
        clustering_service.refresh(list(self._sessions.values()))
        return self._scoring_engine.build_report(
            session_id,
            session.state,
            runtime_ai_config,
            naming_style,
        )

    def build_map(self, session_id: str, projection_mode: str = "auto") -> dict[str, object]:
        session = self.get_session(session_id)
        if session.state.question_count < settings.min_questions_for_report:
            raise ValueError("report_not_ready")
        point_x, point_y = clustering_service.project_state(session.state, projection_mode)
        cluster_name, _narrative_label, _cluster_confidence = clustering_service.cluster_for_state(session.state)
        avg_sigma = sum(session.state.core_sigma.values()) / max(len(session.state.core_sigma), 1)
        confidence = max(0.0, min(1.0, 1 - avg_sigma / 3))
        answer_points: list[dict[str, object]] = []
        trajectory_points: list[dict[str, object]] = []
        replay_state = self._new_state()
        for index, answer in enumerate(session.state.answers, start=1):
            item = self.get_item(answer.item_id)
            answer_x, answer_y = clustering_service.project_template_vector(item.dimension_weights, answer.mapped_score, projection_mode)
            answer_points.append(
                {
                    "x": answer_x,
                    "y": answer_y,
                    "dimensions": item.dimension_weights,
                    "label": f"Q{index} · {item.prompt[:20]}",
                    "kind": "answer",
                }
            )
            replay_state = self._scoring_engine.apply_response(
                replay_state,
                item,
                answer.option_key,
                answer.latency_ms,
            )
            traj_x, traj_y = clustering_service.project_state(replay_state, projection_mode)
            trajectory_points.append(
                {
                    "x": traj_x,
                    "y": traj_y,
                    "dimensions": replay_state.core_mu,
                    "label": f"Q{index}",
                    "kind": "trajectory",
                }
            )

        cluster_centers = [
            {
                "x": center["x"],
                "y": center["y"],
                "dimensions": {},
                "label": center["cluster_name"],
                "kind": "cluster_center",
                "cluster_name": center["cluster_name"],
            }
            for center in clustering_service.center_points(projection_mode)
        ]

        return {
            "session_id": session_id,
            "point": {
                "x": point_x,
                "y": point_y,
                "dimensions": session.state.core_mu,
                "label": "当前画像",
                "kind": "current",
                "cluster_name": cluster_name,
            },
            "confidence": round(confidence, 3),
            "answer_points": answer_points[-40:],
            "trajectory_points": trajectory_points[-40:],
            "cluster_centers": cluster_centers,
            "cluster_regions": clustering_service.cluster_regions(projection_mode),
        }

    def cluster_overview(self) -> ClusterOverview:
        clustering_service.refresh(list(self._sessions.values()))
        return clustering_service.overview(list(self._sessions.values()))

    def save_cluster_label_override(self, version: str, cluster_index: int, name: str, narrative_label: str) -> None:
        clustering_service.save_label_override(version, cluster_index, name, narrative_label)

    def archive_item(self, template_id: str) -> ItemTemplate:
        if template_id not in self._items:
            raise KeyError("template_not_found")
        template = self._items[template_id].model_copy(
            update={"archived": True, "archived_at": datetime.now(UTC)}
        )
        self._items[template_id] = template
        local_session_store.save_template(template)
        vector_indexer.index_template(template)
        return template

    def delete_item(self, template_id: str) -> None:
        if template_id not in self._items:
            raise KeyError("template_not_found")
        if not template_id.startswith("user-"):
            raise ValueError("seed_template_cannot_be_deleted")
        self._items.pop(template_id, None)
        local_session_store.delete_template(template_id)
        vector_indexer.delete_template(template_id)

    def build_summary(self, session_id: str) -> SessionSummary:
        session = self.get_session(session_id)
        return SessionSummary(
            session_id=session.session_id,
            question_count=session.state.question_count,
            min_questions_for_report=settings.min_questions_for_report,
            max_questions_per_session=settings.max_questions_per_session,
            can_generate_report=session.state.question_count >= settings.min_questions_for_report,
            remaining_until_report=max(settings.min_questions_for_report - session.state.question_count, 0),
            current_item_id=session.current_item_id,
            current_template_id=session.current_template_id,
            state=session.state,
        )

    def build_workbench_checkpoint(self, session_id: str) -> WorkbenchCheckpoint:
        return self._workbench_checkpoint(self.get_session(session_id))

    def build_workbench_evidence(self, session_id: str) -> WorkbenchEvidence:
        session = self.get_session(session_id)
        notes = ["检索证据只用于解释当前选题，不代表最终人格结论。"]
        try:
            current_item = self.get_current_question(session_id)
        except KeyError:
            current_item = None
            notes.append("当前题目记录不可用，题目近邻证据暂不可用。")

        base_payload = {
            "current_question_id": current_item.id if current_item else None,
            "current_template_id": current_item.template_id if current_item else session.current_template_id,
        }
        if not vector_indexer.is_enabled():
            return WorkbenchEvidence(
                **base_payload,
                notes=[*notes, "向量检索当前未启用，因此只展示本地状态解释。"],
            )

        item_hits: list[VectorSearchHit] = []
        session_hits: list[VectorSearchHit] = []
        reranker_applied = False

        if current_item is None:
            notes.append("当前没有待答题目，题目近邻证据暂不可用。")
        else:
            try:
                source_template = self._items.get(current_item.template_id)
                retrieval_context = vector_indexer.build_rewrite_retrieval_context(source_template) if source_template else None
                if retrieval_context is not None:
                    item_hits = [
                        *retrieval_context.template_hits,
                        *retrieval_context.item_instance_hits,
                        *retrieval_context.rewrite_candidate_hits,
                    ]
                    reranker_applied = retrieval_context.reranker_applied or self._any_reranked(item_hits)
                else:
                    item_hits = vector_indexer.search_similar_templates(prompt=current_item.prompt, top_k=4)
                    reranker_applied = self._any_reranked(item_hits)
            except Exception:
                notes.append("题目近邻检索暂不可用，已保留主答题流程。")

        try:
            session_hits = vector_indexer.search_similar_sessions(session, top_k=3)
            reranker_applied = reranker_applied or self._any_reranked(session_hits)
        except Exception:
            notes.append("相似会话检索暂不可用，已保留主答题流程。")

        filtered_item_hits = [
            hit
            for hit in item_hits
            if current_item is None or hit.object_id not in {current_item.id, current_item.template_id}
        ][:6]

        if not filtered_item_hits:
            notes.append("没有找到足够稳定的相近题目证据。")
        if not session_hits:
            notes.append("没有可展示的相似会话快照；通常需要命中 5 / 10 / 20 / 40 题 milestone 后才会出现。")

        return WorkbenchEvidence(
            **base_payload,
            enabled=True,
            vector_available=True,
            reranker_applied=reranker_applied,
            item_evidence=[self._workbench_evidence_item(hit) for hit in filtered_item_hits],
            session_evidence=[self._workbench_evidence_item(hit) for hit in session_hits[:3]],
            notes=notes,
        )

    def get_current_question(self, session_id: str) -> ItemInstance | None:
        session = self.get_session(session_id)
        if not session.current_item_id:
            return None
        return self.get_item(session.current_item_id)

    def discard_session(self, session_id: str) -> None:
        _session = self.get_session(session_id)
        local_session_store.delete_session(session_id)
        vector_indexer.delete_session_snapshots(session_id)
        self._sessions.pop(session_id, None)

    def _recent_template_ids(self, session: SessionRecord) -> set[str]:
        recent = set(session.state.recent_item_ids)
        recent.update(answer.template_id for answer in session.state.answers[-settings.exact_repeat_cooldown :])
        if session.current_template_id:
            recent.add(session.current_template_id)
        return recent

    def _live_templates_for_session(self, session: SessionRecord) -> list[ItemTemplate]:
        items = [item for item in self._items.values() if not item.archived]
        if session.mode == "custom":
            return items
        return [item for item in items if not item.id.startswith("user-")]

    def _prompt_for_item(self, item_id: str) -> str | None:
        try:
            return self.get_item(item_id).prompt
        except KeyError:
            return None

    def _recent_scenario_tags(self, session: SessionRecord, window: int) -> set[str]:
        tags: set[str] = set()
        for answer in session.state.answers[-window:]:
            try:
                item = self.get_item(answer.item_id)
            except KeyError:
                continue
            tags.update(item.scenario_tags)
        return tags

    def _recent_generation_modes(self, session: SessionRecord, window: int) -> list[str]:
        modes: list[str] = []
        for answer in session.state.answers[-window:]:
            try:
                item = self.get_item(answer.item_id)
            except KeyError:
                continue
            modes.append(item.generation_mode)
        return modes

    def _recent_probe_ratio(self, session: SessionRecord, window: int) -> float:
        recent_answers = session.state.answers[-window:]
        if not recent_answers:
            return 0.0
        probe_count = sum(1 for answer in recent_answers if answer.template_id.startswith("probe-"))
        return probe_count / len(recent_answers)

    def _recent_contrast_ratio(self, session: SessionRecord, window: int) -> float:
        recent_answers = session.state.answers[-window:]
        if not recent_answers:
            return 0.0
        contrast_count = 0
        total = 0
        for answer in recent_answers:
            try:
                item = self.get_item(answer.item_id)
            except KeyError:
                continue
            if item.layer != "probe":
                continue
            total += 1
            if item.question_type == "contrast_5":
                contrast_count += 1
        if total == 0:
            return 0.0
        return contrast_count / total

    def _preferred_probe_mode(self, session: SessionRecord, runtime_ai_config: AIProviderConfig | None) -> str:
        active_ai_config = runtime_ai_config or ai_service.get_config()
        if active_ai_config is None:
            return "statement"
        return "contrast" if self._recent_contrast_ratio(session, 12) < settings.ai_contrast_target_ratio else "statement"

    def _workbench_checkpoint(self, session: SessionRecord) -> WorkbenchCheckpoint:
        question_count = session.state.question_count
        milestones = self._session_vector_milestones()
        previous_milestone = max((milestone for milestone in milestones if milestone <= question_count), default=None)
        next_milestone = min((milestone for milestone in milestones if milestone > question_count), default=None)
        previous_floor = previous_milestone or 0
        milestone_ceiling = next_milestone or previous_milestone or max(milestones or (settings.min_questions_for_report,))
        if milestone_ceiling == previous_floor:
            milestone_progress = 100.0
        else:
            milestone_progress = self._percent((question_count - previous_floor) / (milestone_ceiling - previous_floor))

        report_ready = question_count >= settings.min_questions_for_report
        remaining_until_report = max(settings.min_questions_for_report - question_count, 0)
        report_progress = 100.0 if report_ready else self._percent(question_count / max(settings.min_questions_for_report, 1))
        snapshot_due_now = question_count in set(milestones)

        return WorkbenchCheckpoint(
            question_count=question_count,
            report_ready=report_ready,
            report_target=settings.min_questions_for_report,
            remaining_until_report=remaining_until_report,
            report_progress_percent=round(report_progress, 1),
            previous_milestone=previous_milestone,
            next_milestone=next_milestone,
            milestone_progress_percent=round(milestone_progress, 1),
            snapshot_due_now=snapshot_due_now,
            narrative=self._workbench_narrative(session, report_ready, next_milestone),
            top_core_signals=self._top_core_workbench_signals(session),
            uncertainty_queue=self._uncertainty_workbench_signals(session),
            active_modules=self._module_workbench_signals(session),
            unlocked_subdimensions=self._subdimension_workbench_signals(session),
            milestones=self._workbench_milestones(question_count, milestones),
        )

    def _workbench_evidence_item(self, hit: VectorSearchHit) -> WorkbenchEvidenceItem:
        label_by_type = {
            "template": "相近模板",
            "item_instance": "历史实例题",
            "rewrite_candidate": "历史改写候选",
            "session_snapshot": "匿名会话快照",
        }
        relationship_by_type = {
            "template": "题库中测量结构接近的模板，可用于解释当前选题方向。",
            "item_instance": "历史生成题中语义接近的实例，用于检查措辞是否过近。",
            "rewrite_candidate": "历史改写候选中的相邻表达，用于避免复制近邻表述。",
            "session_snapshot": "相同 milestone 附近的匿名会话状态，用于观察当前画像是否有近邻。",
        }
        prompt_excerpt = hit.prompt_excerpt.strip()
        if hit.object_type == "session_snapshot":
            milestone = hit.snapshot_milestone or "unknown"
            prompt_excerpt = f"匿名会话快照，Q{milestone} 附近的结构状态摘要。"
        return WorkbenchEvidenceItem(
            reference_key=f"{hit.object_type}:{hashlib.sha1(hit.object_id.encode('utf-8')).hexdigest()[:10]}",
            object_type=hit.object_type,
            label=label_by_type.get(hit.object_type, hit.object_type),
            relationship=relationship_by_type.get(hit.object_type, "语义检索近邻。"),
            prompt_excerpt=prompt_excerpt[:180],
            confidence_tier=self._evidence_confidence_tier(hit),
            scenario_tags=hit.scenario_tags[:4],
            snapshot_milestone=hit.snapshot_milestone,
        )

    def _evidence_confidence_tier(self, hit: VectorSearchHit) -> str:
        metric = hit.rerank_score if hit.rerank_score is not None else hit.score
        if hit.rerank_score is not None:
            if metric >= 0.7:
                return "high"
            if metric >= 0.45:
                return "medium"
            return "low"
        if metric >= 0.84:
            return "high"
        if metric >= 0.72:
            return "medium"
        return "low"

    def _any_reranked(self, hits: list[VectorSearchHit]) -> bool:
        return any(hit.rerank_score is not None for hit in hits)

    def _top_core_workbench_signals(self, session: SessionRecord) -> list[WorkbenchSignal]:
        ordered = sorted(session.state.core_mu.items(), key=lambda item: abs(item[1]), reverse=True)[:5]
        return [
            WorkbenchSignal(
                key=key,
                label=CORE_DIMENSION_LABELS.get(key, key),
                value=round(value, 3),
                confidence_percent=round(self._confidence_from_sigma(session.state.core_sigma.get(key, settings.default_sigma)), 1),
                sample_count=session.state.dimension_counts.get(key, 0),
                detail="当前画像中最突出的核心信号",
            )
            for key, value in ordered
        ]

    def _uncertainty_workbench_signals(self, session: SessionRecord) -> list[WorkbenchSignal]:
        ordered = sorted(session.state.core_sigma.items(), key=lambda item: item[1], reverse=True)[:4]
        return [
            WorkbenchSignal(
                key=key,
                label=CORE_DIMENSION_LABELS.get(key, key),
                value=round(sigma, 3),
                confidence_percent=round(self._confidence_from_sigma(sigma), 1),
                sample_count=session.state.dimension_counts.get(key, 0),
                detail="sigma 越高，越需要后续题目继续压缩误差带",
            )
            for key, sigma in ordered
        ]

    def _module_workbench_signals(self, session: SessionRecord) -> list[WorkbenchSignal]:
        active = set(session.state.active_modules)
        ordered = sorted(
            (
                (key, value)
                for key, value in session.state.module_scores.items()
                if key in active or abs(value) > 0.01
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:4]
        return [
            WorkbenchSignal(
                key=key,
                label=MODULE_LABELS.get(key, key),
                value=round(value, 3),
                confidence_percent=100.0 if key in active else 35.0,
                sample_count=session.state.module_counts.get(key, 0),
                detail="已出现足够场景证据" if key in active else "仍在观察",
            )
            for key, value in ordered
        ]

    def _subdimension_workbench_signals(self, session: SessionRecord) -> list[WorkbenchSignal]:
        ordered = sorted(
            (
                (key, session.state.sub_mu.get(key, 0.0))
                for key in session.state.unlocked_subdimensions
            ),
            key=lambda item: abs(item[1]),
            reverse=True,
        )[:6]
        return [
            WorkbenchSignal(
                key=key,
                label=SUBDIMENSION_LABELS.get(key, key),
                value=round(value, 3),
                confidence_percent=round(self._confidence_from_sigma(session.state.sub_sigma.get(key, settings.default_sigma)), 1),
                sample_count=session.state.sub_counts.get(key, 0),
                detail=f"父维度：{CORE_DIMENSION_LABELS.get(SUBDIMENSION_TO_PARENT.get(key, ''), SUBDIMENSION_TO_PARENT.get(key, 'unknown'))}",
            )
            for key, value in ordered
        ]

    def _workbench_milestones(self, question_count: int, milestones: tuple[int, ...]) -> list[WorkbenchMilestone]:
        rows: list[WorkbenchMilestone] = []
        next_milestone = min((milestone for milestone in milestones if milestone > question_count), default=None)
        for milestone in milestones:
            if question_count >= milestone:
                status = "completed"
                progress = 100.0
            elif milestone == next_milestone:
                status = "current"
                previous = max((value for value in milestones if value < milestone), default=0)
                progress = self._percent((question_count - previous) / max(milestone - previous, 1))
            else:
                status = "upcoming"
                progress = 0.0
            rows.append(
                WorkbenchMilestone(
                    milestone=milestone,
                    status=status,  # type: ignore[arg-type]
                    question_delta=max(milestone - question_count, 0),
                    progress_percent=round(progress, 1),
                    snapshot_expected=question_count == milestone,
                )
            )
        return rows

    def _workbench_narrative(self, session: SessionRecord, report_ready: bool, next_milestone: int | None) -> str:
        if session.state.question_count == 0:
            return "会话刚开始，系统正在建立第一批核心维度信号。"
        top_signal = max(session.state.core_mu.items(), key=lambda item: abs(item[1]))
        uncertain = max(session.state.core_sigma.items(), key=lambda item: item[1])
        parts = [
            f"当前最突出的信号是 {CORE_DIMENSION_LABELS.get(top_signal[0], top_signal[0])}。",
            f"最需要继续压缩误差带的是 {CORE_DIMENSION_LABELS.get(uncertain[0], uncertain[0])}。",
        ]
        if report_ready:
            parts.append("正式报告已经解锁，可以先查看，也可以继续细化画像。")
        elif next_milestone is not None:
            parts.append(f"下一次会话快照会在第 {next_milestone} 题写入向量层。")
        return "".join(parts)

    def _session_vector_milestones(self) -> tuple[int, ...]:
        raw_values = [value.strip() for value in settings.session_vector_milestones.split(",")]
        parsed = sorted({int(value) for value in raw_values if value})
        return tuple(value for value in parsed if value > 0)

    def _confidence_from_sigma(self, sigma: float) -> float:
        return self._percent(1 - sigma / max(settings.default_sigma, 0.01))

    def _percent(self, ratio: float) -> float:
        return max(0.0, min(100.0, ratio * 100.0))


session_service = SessionService()
