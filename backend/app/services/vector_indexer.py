"""Best-effort vector indexing and retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from math import sqrt
from typing import Literal
from uuid import uuid4

from qdrant_client.http import models

from app.core.config import settings
from app.domain.dimensions import (
    MODULE_KEYS,
    SUBDIMENSION_TO_PARENT,
    make_zero_module_vector,
    make_zero_subdimension_vector,
    make_zero_vector,
)
from app.domain.item_bank import build_seed_item_bank
from app.domain.models import (
    EmbeddingScoreBreakdown,
    ItemInstance,
    ItemTemplate,
    RewriteCandidate,
    RewriteRetrievalContext,
    SessionRecord,
    SessionState,
    VectorReindexSummary,
    VectorSearchHit,
    VectorSyncFailure,
)
from app.services.embedding_service import EmbeddingDocument, EmbeddingServiceError, embedding_service
from app.services.reranker_service import RerankerServiceError, reranker_service
from app.services.scoring import ScoringEngine
from app.services.storage import local_session_store
from app.services.vector_store import VectorStoreError, vector_store


ReindexScope = Literal["templates", "instances", "sessions", "all"]


class VectorIndexer:
    def __init__(self) -> None:
        self._scoring_engine = ScoringEngine()

    def is_enabled(self) -> bool:
        return embedding_service.is_enabled() and vector_store.is_enabled()

    def index_template(self, template: ItemTemplate) -> str | None:
        return self._upsert_document(
            operation="index_template",
            object_type="template",
            object_id=template.id,
            payload={"template_id": template.id},
            document_builder=lambda: embedding_service.build_template_document(template),
            collection_name=self._item_collection_name(),
        )

    def delete_template(self, template_id: str) -> str | None:
        return self._perform_delete(
            point_id=template_id,
            object_type="template",
            object_id=template_id,
            operation="delete_template",
            collection_name=self._item_collection_name(),
        )

    def index_item_instance(self, instance: ItemInstance) -> str | None:
        return self._upsert_document(
            operation="index_item_instance",
            object_type="item_instance",
            object_id=instance.id,
            payload={"instance_id": instance.id, "template_id": instance.template_id},
            document_builder=lambda: embedding_service.build_item_instance_document(instance),
            collection_name=self._item_collection_name(),
        )

    def index_rewrite_candidate(
        self,
        template: ItemTemplate,
        candidate: RewriteCandidate,
        candidate_status: str,
    ) -> str | None:
        return self._upsert_document(
            operation="index_rewrite_candidate",
            object_type="rewrite_candidate",
            object_id=f"{template.id}:{candidate_status}:{candidate.rewritten_prompt[:24]}",
            payload={
                "template_id": template.id,
                "candidate_status": candidate_status,
                "generation_mode": candidate.generation_mode,
            },
            document_builder=lambda: embedding_service.build_rewrite_candidate_document(
                template,
                candidate.rewritten_prompt,
                candidate.generation_mode,
                candidate.validator_passed,
                candidate_status,
            ),
            collection_name=self._item_collection_name(),
        )

    def index_session_snapshot(
        self,
        session: SessionRecord,
        snapshot_milestone: int | None = None,
    ) -> str | None:
        resolved_milestone = snapshot_milestone or self._matching_session_milestone(session.state.question_count)
        if resolved_milestone is None:
            return None
        object_id = f"{session.session_id}:{resolved_milestone}"
        return self._upsert_document(
            operation="index_session_snapshot",
            object_type="session_snapshot",
            object_id=object_id,
            payload={
                "session_id": session.session_id,
                "snapshot_milestone": resolved_milestone,
                "question_count": session.state.question_count,
            },
            document_builder=lambda: embedding_service.build_session_snapshot_document(session, resolved_milestone),
            collection_name=self._session_collection_name(),
        )

    def delete_session_snapshots(self, session_id: str) -> str | None:
        if not self.is_enabled():
            return None
        try:
            vector_store.delete_by_filter(
                self._build_filter(object_types=["session_snapshot"], session_id=session_id),
                collection_name=self._session_collection_name(),
            )
            return None
        except Exception as exc:  # pragma: no cover - covered by unit tests via mocks
            return self._record_failure(
                object_type="session_snapshot",
                object_id=session_id,
                operation="delete_session_snapshots",
                error_message=str(exc),
                payload_json=json.dumps({"session_id": session_id}, ensure_ascii=False),
            )

    def search_similar_templates(
        self,
        *,
        template: ItemTemplate | None = None,
        prompt: str | None = None,
        top_k: int | None = None,
    ) -> list[VectorSearchHit]:
        if template is None and not prompt:
            return []
        natural_query = template.prompt if template is not None else str(prompt or "")
        query_text = (
            embedding_service.build_template_document(template).text
            if template is not None
            else embedding_service.build_search_text(natural_query)
        )
        exclude_object_id = template.id if template is not None else None
        return self._search_hits(
            query_text=query_text,
            natural_query=natural_query,
            top_k=top_k or settings.vector_search_top_k,
            object_types=["template"],
            exclude_object_id=exclude_object_id,
            collection_name=self._item_collection_name(),
        )

    def search_similar_sessions(
        self,
        session: SessionRecord,
        top_k: int | None = None,
    ) -> list[VectorSearchHit]:
        snapshot_milestone = self._latest_session_milestone(session.state.question_count)
        if snapshot_milestone is None:
            return []
        document = embedding_service.build_session_snapshot_document(session, snapshot_milestone)
        return self._search_hits(
            query_text=document.text,
            natural_query=document.prompt,
            top_k=top_k or settings.session_vector_top_k,
            object_types=["session_snapshot"],
            exclude_object_id=document.point_id,
            snapshot_milestone=snapshot_milestone,
            collection_name=self._session_collection_name(),
        )

    def build_rewrite_retrieval_context(self, template: ItemTemplate) -> RewriteRetrievalContext | None:
        if not self.is_enabled():
            return None
        template_document = embedding_service.build_template_document(template)
        return RewriteRetrievalContext(
            enabled=True,
            reranker_applied=reranker_service.is_enabled(),
            template_hits=self._search_hits(
                query_text=template_document.text,
                natural_query=template.prompt,
                top_k=min(3, settings.vector_search_top_k),
                object_types=["template"],
                exclude_object_id=template.id,
                collection_name=self._item_collection_name(),
            ),
            item_instance_hits=self._search_hits(
                query_text=template_document.text,
                natural_query=template.prompt,
                top_k=min(3, settings.vector_search_top_k),
                object_types=["item_instance"],
                collection_name=self._item_collection_name(),
            ),
            rewrite_candidate_hits=self._search_hits(
                query_text=template_document.text,
                natural_query=template.prompt,
                top_k=min(3, settings.vector_search_top_k),
                object_types=["rewrite_candidate"],
                collection_name=self._item_collection_name(),
            ),
        )

    def score_rewrite_candidate(
        self,
        template: ItemTemplate,
        prompt: str,
        generation_mode: str,
    ) -> EmbeddingScoreBreakdown | None:
        if not self.is_enabled():
            return None
        try:
            source_text = embedding_service.build_template_document(template).text
            candidate_text = embedding_service.build_rewrite_candidate_document(
                template=template,
                rewritten_prompt=prompt,
                generation_mode=generation_mode,
                validator_passed=True,
                candidate_status="candidate",
            ).text
            source_vector, candidate_vector = embedding_service.embed_texts([source_text, candidate_text])
            source_similarity = self._cosine_similarity(source_vector, candidate_vector)

            duplicate_hits = vector_store.search(
                candidate_vector,
                limit=max(settings.vector_search_top_k, 5),
                score_threshold=settings.vector_search_score_threshold,
                query_filter=self._build_filter(
                    object_types=["template", "item_instance", "rewrite_candidate"],
                    exclude_object_id=template.id,
                ),
                collection_name=self._item_collection_name(),
            )
            duplicate_similarity = max((float(hit.score) for hit in duplicate_hits), default=0.0)

            alignment_hits = vector_store.search(
                candidate_vector,
                limit=max(settings.vector_search_top_k, 5),
                score_threshold=settings.vector_search_score_threshold,
                query_filter=self._build_filter(
                    object_types=["template", "item_instance"],
                    layer=template.layer,
                    dimension_keys=list(template.dimension_weights),
                    exclude_object_id=template.id,
                ),
                collection_name=self._item_collection_name(),
            )
            alignment_similarity = max((float(hit.score) for hit in alignment_hits), default=0.0)
        except (EmbeddingServiceError, VectorStoreError):
            return None

        if 0.78 <= source_similarity <= 0.94:
            source_distance_score = 0.9
        elif source_similarity > 0.97:
            source_distance_score = -1.1
        elif source_similarity < 0.55:
            source_distance_score = -0.8
        else:
            source_distance_score = 0.15

        duplicate_penalty = round(max(0.0, (duplicate_similarity - 0.88) * 6.5), 3)
        if alignment_similarity >= 0.84:
            alignment_bonus = 0.55
        elif alignment_similarity >= 0.74:
            alignment_bonus = 0.25
        else:
            alignment_bonus = 0.0

        total = round(source_distance_score - duplicate_penalty + alignment_bonus, 3)
        return EmbeddingScoreBreakdown(
            enabled=True,
            source_similarity=round(source_similarity, 3),
            source_distance_score=round(source_distance_score, 3),
            duplicate_similarity=round(duplicate_similarity, 3),
            duplicate_penalty=duplicate_penalty,
            alignment_similarity=round(alignment_similarity, 3),
            alignment_bonus=round(alignment_bonus, 3),
            total=total,
        )

    def reindex(self, scope: ReindexScope) -> VectorReindexSummary:
        summary = VectorReindexSummary(scope=scope, enabled=self.is_enabled())
        if not self.is_enabled():
            return summary

        if scope in {"templates", "all"}:
            self._clear_scope("template", collection_name=self._item_collection_name())
            template_map = {template.id: template for template in build_seed_item_bank()}
            template_map.update({template.id: template for template in local_session_store.load_templates()})
            for template in template_map.values():
                failure_id = self.index_template(template)
                if failure_id:
                    summary.failed_count += 1
                    summary.failure_ids.append(failure_id)
                else:
                    summary.indexed_count += 1

        if scope in {"instances", "all"}:
            self._clear_scope("item_instance", collection_name=self._item_collection_name())
            for instance in local_session_store.list_item_instances(limit=None):
                failure_id = self.index_item_instance(instance)
                if failure_id:
                    summary.failed_count += 1
                    summary.failure_ids.append(failure_id)
                else:
                    summary.indexed_count += 1

        if scope in {"sessions", "all"}:
            self._clear_scope("session_snapshot", collection_name=self._session_collection_name())
            for session in local_session_store.list_session_records(limit=None):
                for snapshot in self._session_snapshots_for_reindex(session):
                    failure_id = self.index_session_snapshot(snapshot, snapshot.state.question_count)
                    if failure_id:
                        summary.failed_count += 1
                        summary.failure_ids.append(failure_id)
                    else:
                        summary.indexed_count += 1
        return summary

    def _clear_scope(self, object_type: str, *, collection_name: str) -> None:
        if not self.is_enabled():
            return
        try:
            vector_store.delete_by_filter(
                self._build_filter(object_types=[object_type]),
                collection_name=collection_name,
            )
        except VectorStoreError:
            return

    def _search_hits(
        self,
        *,
        query_text: str,
        natural_query: str,
        top_k: int,
        object_types: list[str],
        exclude_object_id: str | None = None,
        layer: str | None = None,
        dimension_keys: list[str] | None = None,
        snapshot_milestone: int | None = None,
        collection_name: str,
    ) -> list[VectorSearchHit]:
        if not self.is_enabled():
            return []
        search_limit = top_k if not reranker_service.is_enabled() else max(top_k * 2, top_k + 2)
        try:
            vector = embedding_service.embed_texts([query_text])[0]
            hits = vector_store.search(
                vector,
                limit=search_limit,
                score_threshold=settings.vector_search_score_threshold,
                query_filter=self._build_filter(
                    object_types=object_types,
                    exclude_object_id=exclude_object_id,
                    layer=layer,
                    dimension_keys=dimension_keys,
                    snapshot_milestone=snapshot_milestone,
                ),
                collection_name=collection_name,
            )
            reranked_hits = self._rerank_hits(natural_query, hits, top_k)
        except (EmbeddingServiceError, VectorStoreError):
            return []
        return [self._map_hit(hit, rerank_score=rerank_score) for hit, rerank_score in reranked_hits[:top_k]]

    def _rerank_hits(
        self,
        query: str,
        hits: list[models.ScoredPoint],
        top_k: int,
    ) -> list[tuple[models.ScoredPoint, float | None]]:
        ordered_hits = [(hit, None) for hit in hits]
        if not hits or not reranker_service.is_enabled():
            return ordered_hits
        documents = [str((hit.payload or {}).get("prompt", "")).strip() for hit in hits]
        if not any(documents):
            return ordered_hits
        try:
            results = reranker_service.rerank(query, documents, top_n=min(top_k, len(documents)))
        except RerankerServiceError:
            return ordered_hits

        reranked: list[tuple[models.ScoredPoint, float | None]] = []
        used_indexes: set[int] = set()
        for result in results:
            if 0 <= result.index < len(hits):
                reranked.append((hits[result.index], round(result.relevance_score, 3)))
                used_indexes.add(result.index)
        reranked.extend((hit, None) for index, hit in enumerate(hits) if index not in used_indexes)
        return reranked

    def _map_hit(self, hit: models.ScoredPoint, *, rerank_score: float | None = None) -> VectorSearchHit:
        payload = hit.payload or {}
        prompt = str(payload.get("prompt", ""))
        milestone = payload.get("snapshot_milestone")
        return VectorSearchHit(
            object_id=str(payload.get("object_id", hit.id)),
            object_type=str(payload.get("object_type", "template")),  # type: ignore[arg-type]
            template_id=self._nullable_str(payload.get("template_id")),
            instance_id=self._nullable_str(payload.get("instance_id")),
            session_id=self._nullable_str(payload.get("session_id")),
            snapshot_milestone=int(milestone) if milestone is not None else None,
            layer=str(payload.get("layer", "core")),
            generation_mode=str(payload.get("generation_mode", "template")),
            prompt_excerpt=prompt[:160],
            score=round(float(hit.score), 3),
            rerank_score=rerank_score,
            scenario_tags=[str(tag) for tag in payload.get("scenario_tags", [])],
        )

    def _upsert_document(
        self,
        *,
        operation: str,
        object_type: str,
        object_id: str,
        payload: dict[str, object],
        document_builder,
        collection_name: str,
    ) -> str | None:
        if not self.is_enabled():
            return None
        try:
            document: EmbeddingDocument = document_builder()
            vector = embedding_service.embed_texts([document.text])[0]
            document.payload["updated_at"] = datetime.now(UTC).isoformat()
            vector_store.upsert(document.point_id, vector, document.payload, collection_name=collection_name)
            return None
        except Exception as exc:  # pragma: no cover - covered by unit tests via mocks
            return self._record_failure(
                object_type=object_type,
                object_id=object_id,
                operation=operation,
                error_message=str(exc),
                payload_json=json.dumps(payload, ensure_ascii=False),
            )

    def _perform_delete(
        self,
        *,
        point_id: str,
        object_type: str,
        object_id: str,
        operation: str,
        collection_name: str,
    ) -> str | None:
        if not self.is_enabled():
            return None
        try:
            vector_store.delete_point(point_id, collection_name=collection_name)
            return None
        except Exception as exc:  # pragma: no cover - covered by unit tests via mocks
            return self._record_failure(
                object_type=object_type,
                object_id=object_id,
                operation=operation,
                error_message=str(exc),
                payload_json=json.dumps({"point_id": point_id}, ensure_ascii=False),
            )

    def _record_failure(
        self,
        *,
        object_type: str,
        object_id: str,
        operation: str,
        error_message: str,
        payload_json: str,
    ) -> str:
        failure = VectorSyncFailure(
            failure_id=f"vf-{uuid4()}",
            object_type=object_type,
            object_id=object_id,
            operation=operation,
            error_message=error_message,
            payload_json=payload_json,
            created_at=datetime.now(UTC),
        )
        local_session_store.save_vector_sync_failure(failure)
        return failure.failure_id

    def _build_filter(
        self,
        *,
        object_types: list[str] | None = None,
        exclude_object_id: str | None = None,
        layer: str | None = None,
        dimension_keys: list[str] | None = None,
        session_id: str | None = None,
        snapshot_milestone: int | None = None,
    ) -> models.Filter:
        must: list[models.FieldCondition] = []
        must_not: list[models.FieldCondition] = []
        if object_types:
            if len(object_types) == 1:
                must.append(models.FieldCondition(key="object_type", match=models.MatchValue(value=object_types[0])))
            else:
                must.append(models.FieldCondition(key="object_type", match=models.MatchAny(any=object_types)))
        if layer:
            must.append(models.FieldCondition(key="layer", match=models.MatchValue(value=layer)))
        if dimension_keys:
            must.append(models.FieldCondition(key="dimension_keys", match=models.MatchAny(any=dimension_keys)))
        if session_id:
            must.append(models.FieldCondition(key="session_id", match=models.MatchValue(value=session_id)))
        if snapshot_milestone is not None:
            must.append(models.FieldCondition(key="snapshot_milestone", match=models.MatchValue(value=snapshot_milestone)))
        if exclude_object_id:
            must_not.append(models.FieldCondition(key="object_id", match=models.MatchValue(value=exclude_object_id)))
        return models.Filter(must=must or None, must_not=must_not or None)

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _session_snapshots_for_reindex(self, session: SessionRecord) -> list[SessionRecord]:
        milestones = set(self._session_vector_milestones())
        if not milestones or session.state.question_count < min(milestones):
            return []

        replay_state = self._empty_session_state()
        snapshots: list[SessionRecord] = []
        for answer in session.state.answers:
            item = local_session_store.load_item_instance(answer.item_id)
            if item is None:
                continue
            replay_state = self._scoring_engine.apply_response(
                replay_state,
                item,
                answer.option_key,
                answer.latency_ms,
            )
            if replay_state.question_count in milestones:
                snapshots.append(
                    SessionRecord(
                        session_id=session.session_id,
                        mode=session.mode,
                        status=session.status,
                        state=replay_state.model_copy(deep=True),
                        session_secret_hash=session.session_secret_hash,
                        delete_token_hash=session.delete_token_hash,
                        owner_key=session.owner_key,
                        current_item_id=session.current_item_id,
                        current_template_id=session.current_template_id,
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                    )
                )
        return snapshots

    def _empty_session_state(self) -> SessionState:
        return SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
            module_scores=make_zero_module_vector(0.0),
            module_counts={key: 0 for key in MODULE_KEYS},
            dimension_counts={key: 0 for key in make_zero_vector(0.0)},
        )

    def _session_vector_milestones(self) -> tuple[int, ...]:
        raw_values = [value.strip() for value in settings.session_vector_milestones.split(",")]
        parsed = sorted({int(value) for value in raw_values if value})
        return tuple(value for value in parsed if value > 0)

    def _matching_session_milestone(self, question_count: int) -> int | None:
        milestones = set(self._session_vector_milestones())
        return question_count if question_count in milestones else None

    def _latest_session_milestone(self, question_count: int) -> int | None:
        candidates = [milestone for milestone in self._session_vector_milestones() if milestone <= question_count]
        if not candidates:
            return None
        return candidates[-1]

    def _nullable_str(self, value: object) -> str | None:
        if value is None:
            return None
        rendered = str(value)
        return rendered if rendered else None

    def _item_collection_name(self) -> str:
        return settings.qdrant_collection_item_vectors

    def _session_collection_name(self) -> str:
        return settings.qdrant_collection_session_vectors


vector_indexer = VectorIndexer()
