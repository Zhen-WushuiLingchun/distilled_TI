from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from app.core.config import settings
from app.domain.galgame_calibration import FREE_TEXT_CALIBRATION_CASES, build_calibration_choices
from app.domain.item_bank import build_seed_item_bank
from app.domain.models import (
    EmbeddingScoreBreakdown,
    GalgameChoice,
    GalgameTurn,
    ItemInstance,
    RewriteRetrievalContext,
    SessionRecord,
    SessionState,
    VectorSearchHit,
)
from app.domain.dimensions import make_zero_module_vector, make_zero_subdimension_vector, make_zero_vector
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.embedding_service import EmbeddingServiceError, embedding_service
from app.services.generation import generation_service
from app.services.reranker_service import reranker_service
from app.services.scoring import ScoringEngine
from app.services.storage import local_session_store
from app.services.vector_indexer import vector_indexer
from app.services.vector_store import vector_store


def _enable_vectors(monkeypatch):
    monkeypatch.setattr(settings, "vector_enabled", True)
    monkeypatch.setattr(settings, "embedding_base_url", "https://example.com/v1")
    monkeypatch.setattr(settings, "embedding_model", "demo-embedding")
    monkeypatch.setattr(settings, "embedding_api_key", "secret")
    monkeypatch.setattr(settings, "qdrant_url", "http://127.0.0.1:6333")


def _session() -> SessionRecord:
    return SessionRecord(
        session_id="session-vector-test",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )


def test_template_canonical_text_is_stable():
    template = build_seed_item_bank()[0]

    document = embedding_service.build_template_document(template)

    assert document.point_id == template.id
    assert "object_type=template" in document.text
    assert f"layer={template.layer}" in document.text
    assert "dimensions=" in document.text
    assert "scenarios=" in document.text
    assert f"prompt={template.prompt}" in document.text


def test_session_snapshot_canonical_text_is_stable():
    session = _session()
    session.state.question_count = 5
    session.state.core_mu["execution_drive"] = 1.1
    session.state.core_sigma["planning_preference"] = 0.7
    session.state.active_modules = ["coordination"]
    session.state.unlocked_subdimensions = ["risk_window"]

    document = embedding_service.build_session_snapshot_document(session, snapshot_milestone=5)

    assert document.object_type == "session_snapshot"
    assert "object_type=session_snapshot" in document.text
    assert "snapshot_milestone=5" in document.text
    assert "top_core_mu=" in document.text
    assert "recent_answer_style=" in document.text


def test_galgame_turn_canonical_text_includes_free_text_inference():
    turn = GalgameTurn(
        turn_id="gal-test",
        session_id="session-story",
        item_id="inst-story",
        template_id="core-plan-1",
        scene_id="session-story:inst-story:1",
        selected_option_key="neutral",
        custom_text="我先观察一下所有人的顾虑，再决定要不要推进。",
        scene_text="社团活动室里突然需要有人接手。",
        inferred_option_key="neutral",
        inference_confidence=0.71,
        inference_reason="融合判断",
        classifier_source="hybrid",
        inference_distribution={"neutral": 0.71, "agree": 0.29},
        embedding_similarity={"neutral": 0.64, "agree": 0.36},
        story_template_id="campus-council-window",
        ai_generated=True,
    )

    document = embedding_service.build_galgame_turn_document(turn)

    assert document.object_type == "galgame_turn"
    assert "object_type=galgame_turn" in document.text
    assert "custom_line=我先观察一下" in document.text
    assert "inference_distribution=" in document.text
    assert document.payload["story_template_id"] == "campus-council-window"


def test_embed_texts_returns_provider_vectors(monkeypatch):
    _enable_vectors(monkeypatch)

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ]
            }

    monkeypatch.setattr(httpx.Client, "post", lambda *_args, **_kwargs: _Response())

    vectors = embedding_service.embed_texts(["alpha", "beta"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_texts_wraps_timeout(monkeypatch):
    _enable_vectors(monkeypatch)

    def _raise(*_args, **_kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.Client, "post", _raise)

    with pytest.raises(EmbeddingServiceError):
        embedding_service.embed_texts(["alpha"])


def test_galgame_free_text_classifier_fuses_embedding_without_llm(monkeypatch):
    _enable_vectors(monkeypatch)
    monkeypatch.setattr(ai_service, "_resolve_config", lambda _runtime_config=None: None)
    monkeypatch.setattr(
        embedding_service,
        "embed_texts",
        lambda _texts: [
            [1.0, 0.0, 0.0],
            [0.1, 1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.2, 1.0],
        ],
    )

    choices = [
        GalgameChoice(key="choice-1", text="先退后观察局势", option_key="disagree", score=-0.5, tone="guarded"),
        GalgameChoice(key="choice-2", text="暂时不表态，继续收集信息", option_key="neutral", score=0.0, tone="ambivalent"),
        GalgameChoice(key="choice-3", text="主动推进并接下任务", option_key="agree", score=0.5, tone="direct"),
    ]

    inference = ai_service.classify_galgame_free_text("我先不表态，观察大家真实担心什么。", choices)

    assert inference.source == "hybrid"
    assert inference.embedding_available is True
    assert inference.pairwise_available is True
    assert inference.inferred_option_key == "neutral"
    assert inference.option_scores[0].option_key == "neutral"
    assert inference.option_scores[0].pairwise_score is not None


def test_galgame_free_text_offline_calibration_cases():
    choices = build_calibration_choices()
    results = [
        ai_service.classify_galgame_free_text_offline(case["text"], choices).inferred_option_key == case["expected_option_key"]
        for case in FREE_TEXT_CALIBRATION_CASES
    ]

    assert all(results)


def test_vector_store_uses_qdrant_client_methods(monkeypatch):
    _enable_vectors(monkeypatch)
    calls: dict[str, object] = {}

    class _Client:
        def __init__(self):
            self.exists = False

        def collection_exists(self, _name):
            return self.exists

        def create_collection(self, collection_name, vectors_config):
            calls["create_collection"] = (collection_name, vectors_config.size)
            self.exists = True

        def upsert(self, collection_name, points, wait):
            calls["upsert"] = (collection_name, points[0].id, wait)

        def query_points(self, **kwargs):
            calls["query_points"] = kwargs
            return SimpleNamespace(points=[SimpleNamespace(id="point-1", score=0.91, payload={"object_id": "point-1"})])

        def delete(self, collection_name, points_selector, wait):
            calls["delete"] = (collection_name, type(points_selector).__name__, wait)

    fake_client = _Client()
    monkeypatch.setattr(vector_store, "_client", fake_client)
    monkeypatch.setattr(vector_store, "_collection_ready", False)

    vector_store.upsert("point-1", [0.1, 0.2, 0.3], {"object_id": "point-1"})
    hits = vector_store.search([0.1, 0.2, 0.3], limit=3)
    vector_store.delete_point("point-1")

    assert calls["create_collection"] == (settings.qdrant_collection_item_vectors, 3)
    assert calls["upsert"][0] == settings.qdrant_collection_item_vectors
    assert str(UUID(calls["upsert"][1])) == calls["upsert"][1]
    assert calls["upsert"][2] is True
    assert len(hits) == 1
    assert calls["delete"][0] == settings.qdrant_collection_item_vectors


def test_search_hits_apply_reranker(monkeypatch):
    _enable_vectors(monkeypatch)
    template = build_seed_item_bank()[0]

    monkeypatch.setattr(embedding_service, "embed_texts", lambda _texts: [[0.1, 0.2, 0.3]])
    monkeypatch.setattr(
        vector_store,
        "search",
        lambda *_args, **_kwargs: [
            SimpleNamespace(
                id="hit-a",
                score=0.82,
                payload={"object_id": "hit-a", "object_type": "template", "template_id": "hit-a", "layer": "core", "generation_mode": "template", "prompt": "alpha"},
            ),
            SimpleNamespace(
                id="hit-b",
                score=0.8,
                payload={"object_id": "hit-b", "object_type": "template", "template_id": "hit-b", "layer": "core", "generation_mode": "template", "prompt": "beta"},
            ),
        ],
    )
    monkeypatch.setattr(reranker_service, "is_enabled", lambda: True)
    monkeypatch.setattr(
        reranker_service,
        "rerank",
        lambda _query, _documents, top_n=None: [SimpleNamespace(index=1, relevance_score=0.97), SimpleNamespace(index=0, relevance_score=0.71)],
    )

    hits = vector_indexer.search_similar_templates(template=template, top_k=2)

    assert hits[0].object_id == "hit-b"
    assert hits[0].rerank_score == 0.97


def test_index_template_records_failure_without_blocking(monkeypatch):
    _enable_vectors(monkeypatch)
    template = build_seed_item_bank()[0]
    before = len(local_session_store.list_vector_sync_failures(limit=200))

    monkeypatch.setattr(embedding_service, "embed_texts", lambda _texts: [[0.1, 0.2, 0.3]])
    monkeypatch.setattr(vector_store, "upsert", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("qdrant down")))

    failure_id = vector_indexer.index_template(template)
    after = len(local_session_store.list_vector_sync_failures(limit=200))

    assert failure_id is not None
    assert after == before + 1


def test_session_reindex_replays_milestones(monkeypatch):
    scoring = ScoringEngine()
    template = build_seed_item_bank()[0]
    base_session = _session()
    replay_state = base_session.state

    for index in range(5):
        instance = ItemInstance(
            id=f"inst-session-{index}",
            template_id=template.id,
            session_id=base_session.session_id,
            prompt=template.prompt,
            question_type=template.question_type,
            layer=template.layer,
            dimension_weights=template.dimension_weights,
            subdimension_weights=template.subdimension_weights,
            module_affinities=template.module_affinities,
            discrimination=template.discrimination,
            difficulty=template.difficulty,
            scenario_tags=template.scenario_tags,
            is_anchor=template.is_anchor,
            allow_rewrite=template.allow_rewrite,
            options=template.options,
        )
        local_session_store.save_item_instance(instance)
        replay_state = scoring.apply_response(replay_state, instance, instance.options[-1].key, latency_ms=900)

    session = base_session.model_copy(update={"state": replay_state})
    snapshots = vector_indexer._session_snapshots_for_reindex(session)

    assert snapshots
    assert snapshots[0].state.question_count == 5


def test_preview_rewrite_passes_retrieval_context_to_ai(monkeypatch):
    template = build_seed_item_bank()[0].model_copy(update={"allow_rewrite": True})
    session = _session()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        vector_indexer,
        "build_rewrite_retrieval_context",
        lambda _template: RewriteRetrievalContext(
            enabled=True,
            template_hits=[
                VectorSearchHit(
                    object_id="core-plan-2",
                    object_type="template",
                    template_id="core-plan-2",
                    layer="core",
                    generation_mode="template",
                    prompt_excerpt="邻近模板",
                    score=0.88,
                )
            ],
        ),
    )

    def _rewrite(*_args, **kwargs):
        captured["retrieval_context"] = kwargs.get("retrieval_context")
        return [
            {
                "rewritten_prompt": "当真实约束一压上来时，我通常会先把推进顺序排稳。",
                "generation_mode": "llm_rewrite",
                "validator_passed": True,
            }
        ]

    monkeypatch.setattr(ai_service, "rewrite_template_candidates", _rewrite)
    monkeypatch.setattr(vector_indexer, "index_rewrite_candidate", lambda *_args, **_kwargs: None)

    preview = generation_service.preview_rewrite(
        session,
        template,
        "更高压、更具体",
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
        allow_stored_config=False,
    )

    assert preview.retrieval_context is not None
    assert captured["retrieval_context"]["template_hits"][0]["object_id"] == "core-plan-2"


def test_score_candidate_applies_embedding_breakdown(monkeypatch):
    template = build_seed_item_bank()[0]
    monkeypatch.setattr(
        vector_indexer,
        "score_rewrite_candidate",
        lambda *_args, **_kwargs: EmbeddingScoreBreakdown(
            enabled=True,
            source_similarity=0.85,
            source_distance_score=0.9,
            duplicate_similarity=0.91,
            duplicate_penalty=0.2,
            alignment_similarity=0.87,
            alignment_bonus=0.4,
            total=1.1,
        ),
    )

    candidate = generation_service._score_candidate(
        template,
        "当事情开始变得复杂时，我通常会先把骨架搭出来。",
        "llm_rewrite",
        True,
    )

    assert candidate.embedding_score_breakdown is not None
    assert candidate.embedding_score_breakdown.total == 1.1
    assert any("向量源距离" in reason for reason in candidate.reasons)
