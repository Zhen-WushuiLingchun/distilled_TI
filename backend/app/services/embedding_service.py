"""Embedding helpers and canonical text builders."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from statistics import median
from typing import Any

import httpx

from app.core.config import settings
from app.domain.models import ItemInstance, ItemTemplate, SessionRecord


class EmbeddingServiceError(RuntimeError):
    """Raised when the embedding provider is unavailable."""


@dataclass(slots=True)
class EmbeddingDocument:
    point_id: str
    object_type: str
    prompt: str
    text: str
    payload: dict[str, Any]


class EmbeddingService:
    def is_enabled(self) -> bool:
        return bool(
            settings.vector_enabled
            and settings.embedding_base_url.strip()
            and settings.embedding_model.strip()
            and (settings.qdrant_local_path.strip() or settings.qdrant_url.strip())
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.is_enabled():
            raise EmbeddingServiceError("embedding_not_configured")
        try:
            with httpx.Client(timeout=settings.embedding_timeout_seconds, follow_redirects=False) as client:
                headers = {"Content-Type": "application/json"}
                if settings.embedding_api_key:
                    headers["Authorization"] = f"Bearer {settings.embedding_api_key}"
                response = client.post(
                    f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                    headers=headers,
                    json={
                        "model": settings.embedding_model,
                        "input": texts,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover - exercised by tests via mocks
            raise EmbeddingServiceError(f"embedding_request_failed:{exc}") from exc

        items = payload.get("data")
        if not isinstance(items, list):
            raise EmbeddingServiceError("embedding_response_missing_data")
        vectors: list[list[float]] = []
        for item in sorted(items, key=lambda current: int(current.get("index", 0))):
            embedding = item.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise EmbeddingServiceError("embedding_response_invalid_vector")
            vectors.append([float(value) for value in embedding])
        if len(vectors) != len(texts):
            raise EmbeddingServiceError("embedding_response_count_mismatch")
        return vectors

    def build_template_document(self, template: ItemTemplate) -> EmbeddingDocument:
        payload = self._base_payload(
            object_id=template.id,
            object_type="template",
            template_id=template.id,
            instance_id=None,
            session_id=None,
            prompt=template.prompt,
            layer=template.layer,
            generation_mode="template",
            allow_rewrite=template.allow_rewrite,
            archived=template.archived,
            scenario_tags=template.scenario_tags,
            dimension_weights=template.dimension_weights,
            subdimension_weights=template.subdimension_weights,
            module_affinities=template.module_affinities,
        )
        return EmbeddingDocument(
            point_id=template.id,
            object_type="template",
            prompt=template.prompt,
            text=self._canonical_text(payload),
            payload=payload,
        )

    def build_item_instance_document(self, instance: ItemInstance) -> EmbeddingDocument:
        payload = self._base_payload(
            object_id=instance.id,
            object_type="item_instance",
            template_id=instance.template_id,
            instance_id=instance.id,
            session_id=instance.session_id,
            prompt=instance.prompt,
            layer=instance.layer,
            generation_mode=instance.generation_mode,
            allow_rewrite=instance.allow_rewrite,
            archived=False,
            scenario_tags=instance.scenario_tags,
            dimension_weights=instance.dimension_weights,
            subdimension_weights=instance.subdimension_weights,
            module_affinities=instance.module_affinities,
        )
        return EmbeddingDocument(
            point_id=instance.id,
            object_type="item_instance",
            prompt=instance.prompt,
            text=self._canonical_text(payload),
            payload=payload,
        )

    def build_rewrite_candidate_document(
        self,
        template: ItemTemplate,
        rewritten_prompt: str,
        generation_mode: str,
        validator_passed: bool,
        candidate_status: str,
    ) -> EmbeddingDocument:
        prompt_hash = sha256(
            f"{template.id}|{generation_mode}|{candidate_status}|{rewritten_prompt}".encode("utf-8")
        ).hexdigest()
        point_id = f"rewrite-{template.id}-{prompt_hash[:20]}"
        payload = self._base_payload(
            object_id=point_id,
            object_type="rewrite_candidate",
            template_id=template.id,
            instance_id=None,
            session_id=None,
            prompt=rewritten_prompt,
            layer=template.layer,
            generation_mode=generation_mode,
            allow_rewrite=template.allow_rewrite,
            archived=False,
            scenario_tags=template.scenario_tags,
            dimension_weights=template.dimension_weights,
            subdimension_weights=template.subdimension_weights,
            module_affinities=template.module_affinities,
        )
        payload.update(
            {
                "candidate_status": candidate_status,
                "validator_passed": validator_passed,
                "source_template_prompt_hash": sha256(template.prompt.encode("utf-8")).hexdigest(),
            }
        )
        return EmbeddingDocument(
            point_id=point_id,
            object_type="rewrite_candidate",
            prompt=rewritten_prompt,
            text=self._canonical_text(payload),
            payload=payload,
        )

    def build_search_text(
        self,
        prompt: str,
        layer: str = "core",
        dimension_weights: dict[str, float] | None = None,
        subdimension_weights: dict[str, float] | None = None,
        module_affinities: dict[str, float] | None = None,
        scenario_tags: list[str] | None = None,
        generation_mode: str = "query",
        object_type: str = "query",
    ) -> str:
        payload = self._base_payload(
            object_id=f"query-{sha256(prompt.encode('utf-8')).hexdigest()[:12]}",
            object_type=object_type,
            template_id=None,
            instance_id=None,
            session_id=None,
            prompt=prompt,
            layer=layer,
            generation_mode=generation_mode,
            allow_rewrite=False,
            archived=False,
            scenario_tags=scenario_tags or [],
            dimension_weights=dimension_weights or {},
            subdimension_weights=subdimension_weights or {},
            module_affinities=module_affinities or {},
        )
        return self._canonical_text(payload)

    def build_session_snapshot_document(
        self,
        session: SessionRecord,
        snapshot_milestone: int,
    ) -> EmbeddingDocument:
        summary_prompt = self._session_summary_prompt(session, snapshot_milestone)
        top_core_mu = self._top_pairs(session.state.core_mu, 3, absolute=True)
        top_core_sigma = self._top_pairs(session.state.core_sigma, 3, absolute=False)
        payload = {
            "object_id": f"session-snapshot-{session.session_id}-{snapshot_milestone}",
            "object_type": "session_snapshot",
            "template_id": None,
            "instance_id": None,
            "session_id": session.session_id,
            "layer": "session",
            "generation_mode": "session_snapshot",
            "allow_rewrite": False,
            "archived": False,
            "prompt": summary_prompt,
            "scenario_tags": [],
            "dimension_keys": sorted(session.state.core_mu),
            "subdimension_keys": sorted(session.state.unlocked_subdimensions),
            "module_keys": sorted(session.state.active_modules),
            "question_count": session.state.question_count,
            "snapshot_milestone": snapshot_milestone,
            "top_core_mu": self._format_weight_pairs(top_core_mu),
            "top_core_sigma": self._format_weight_pairs(top_core_sigma),
            "core_mu": self._format_weight_pairs(session.state.core_mu),
            "core_sigma": self._format_weight_pairs(session.state.core_sigma),
            "zeta": self._format_weight_pairs(session.state.zeta),
            "active_modules": sorted(session.state.active_modules),
            "unlocked_subdimensions": sorted(session.state.unlocked_subdimensions),
            "extreme_ratio": round(self._extreme_ratio(session), 3),
            "median_latency": round(self._median_latency(session), 3),
            "recent_answer_style": self._recent_answer_style(session),
            "created_at": session.updated_at.isoformat(),
        }
        return EmbeddingDocument(
            point_id=str(payload["object_id"]),
            object_type="session_snapshot",
            prompt=summary_prompt,
            text=self._session_canonical_text(payload),
            payload=payload,
        )

    def _base_payload(
        self,
        *,
        object_id: str,
        object_type: str,
        template_id: str | None,
        instance_id: str | None,
        session_id: str | None,
        prompt: str,
        layer: str,
        generation_mode: str,
        allow_rewrite: bool,
        archived: bool,
        scenario_tags: list[str],
        dimension_weights: dict[str, float],
        subdimension_weights: dict[str, float],
        module_affinities: dict[str, float],
    ) -> dict[str, Any]:
        return {
            "object_id": object_id,
            "object_type": object_type,
            "template_id": template_id,
            "instance_id": instance_id,
            "session_id": session_id,
            "layer": layer,
            "generation_mode": generation_mode,
            "allow_rewrite": allow_rewrite,
            "archived": archived,
            "prompt": prompt,
            "scenario_tags": sorted({tag for tag in scenario_tags if tag}),
            "dimension_keys": sorted(dimension_weights),
            "dimension_weights": self._format_weight_pairs(dimension_weights),
            "subdimension_keys": sorted(subdimension_weights),
            "subdimension_weights": self._format_weight_pairs(subdimension_weights),
            "module_keys": sorted(module_affinities),
            "module_affinities": self._format_weight_pairs(module_affinities),
        }

    def _canonical_text(self, payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"object_type={payload['object_type']}",
                f"layer={payload['layer']}",
                f"dimensions={payload['dimension_weights']}",
                f"subdimensions={payload['subdimension_weights']}",
                f"modules={payload['module_affinities']}",
                f"scenarios={','.join(payload['scenario_tags'])}",
                f"generation_mode={payload['generation_mode']}",
                f"prompt={payload['prompt']}",
            ]
        )

    def _session_canonical_text(self, payload: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"object_type={payload['object_type']}",
                f"session_id={payload['session_id']}",
                f"question_count={payload['question_count']}",
                f"snapshot_milestone={payload['snapshot_milestone']}",
                f"top_core_mu={payload['top_core_mu']}",
                f"top_core_sigma={payload['top_core_sigma']}",
                f"zeta={payload['zeta']}",
                f"active_modules={','.join(payload['active_modules'])}",
                f"unlocked_subdimensions={','.join(payload['unlocked_subdimensions'])}",
                f"extreme_ratio={payload['extreme_ratio']}",
                f"median_latency={payload['median_latency']}",
                f"recent_answer_style={payload['recent_answer_style']}",
                f"prompt={payload['prompt']}",
            ]
        )

    def _format_weight_pairs(self, mapping: dict[str, float]) -> str:
        if not mapping:
            return ""
        return ",".join(f"{key}:{mapping[key]:.3f}" for key in sorted(mapping))

    def _top_pairs(
        self,
        mapping: dict[str, float],
        limit: int,
        *,
        absolute: bool,
    ) -> dict[str, float]:
        ordered = sorted(
            mapping.items(),
            key=lambda item: abs(item[1]) if absolute else item[1],
            reverse=True,
        )[:limit]
        return {key: value for key, value in ordered}

    def _session_summary_prompt(self, session: SessionRecord, snapshot_milestone: int) -> str:
        top_core_mu = self._format_weight_pairs(self._top_pairs(session.state.core_mu, 3, absolute=True))
        top_core_sigma = self._format_weight_pairs(self._top_pairs(session.state.core_sigma, 3, absolute=False))
        return (
            f"session milestone {snapshot_milestone}; "
            f"top_core_mu={top_core_mu}; "
            f"top_core_sigma={top_core_sigma}; "
            f"zeta={self._format_weight_pairs(session.state.zeta)}; "
            f"active_modules={','.join(sorted(session.state.active_modules))}; "
            f"unlocked_subdimensions={','.join(sorted(session.state.unlocked_subdimensions))}; "
            f"extreme_ratio={self._extreme_ratio(session):.3f}; "
            f"median_latency={self._median_latency(session):.1f}; "
            f"recent_answer_style={self._recent_answer_style(session)}"
        )

    def _median_latency(self, session: SessionRecord) -> float:
        values = [answer.latency_ms for answer in session.state.answers if answer.latency_ms is not None]
        if not values:
            return 2500.0
        return float(median(values))

    def _extreme_ratio(self, session: SessionRecord) -> float:
        if not session.state.answers:
            return 0.0
        extreme_count = sum(1 for answer in session.state.answers if abs(answer.mapped_score) >= 1.0)
        return extreme_count / len(session.state.answers)

    def _recent_answer_style(self, session: SessionRecord) -> str:
        recent_answers = session.state.answers[-6:]
        if not recent_answers:
            return "insufficient_history"
        recent_latency = [answer.latency_ms for answer in recent_answers if answer.latency_ms is not None]
        median_recent_latency = float(median(recent_latency)) if recent_latency else 2500.0
        pace = "fast" if median_recent_latency < 1800 else "deliberate" if median_recent_latency < 3200 else "slow"
        extreme_ratio = sum(1 for answer in recent_answers if abs(answer.mapped_score) >= 1.0) / len(recent_answers)
        polarity = "polarized" if extreme_ratio >= 0.6 else "balanced"
        consistency = session.state.zeta.get("consistency", 0.5)
        stability = "steady" if consistency >= 0.6 else "adaptive"
        return f"{pace}_{polarity}_{stability}"


embedding_service = EmbeddingService()
