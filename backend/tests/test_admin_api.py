from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.admin_main import app as admin_app
from app.domain.item_bank import build_seed_item_bank
from app.main import app as public_app
from app.domain.models import RewriteRetrievalContext, VectorReindexSummary, VectorSearchHit, VectorSyncFailure
from app.services.ai_service import ai_service
from app.services.vector_indexer import vector_indexer
from app.services.storage import local_session_store

admin_client = TestClient(admin_app)
public_client = TestClient(public_app)


def test_admin_can_configure_ai_provider_without_exposing_key():
    original = ai_service.test_config
    ai_service.test_config = lambda _config: (True, "AI connection ok.")
    try:
        response = admin_client.post(
            "/api/ai/config",
            json={
                "provider": "deepseek",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "api_key": "secret-key",
            },
        )
    finally:
        ai_service.test_config = original

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["tested"] is True
    assert "api_key" not in payload

    status_response = admin_client.get("/api/ai/config")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["configured"] is True
    assert status_payload["provider"] == "deepseek"


def test_admin_can_issue_session_access_and_preview_rewrite():
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    payload = start_response.json()

    original = vector_indexer.build_rewrite_retrieval_context
    vector_indexer.build_rewrite_retrieval_context = lambda _template: RewriteRetrievalContext(
        enabled=True,
        template_hits=[
            VectorSearchHit(
                object_id="seed-neighbor",
                object_type="template",
                template_id="seed-neighbor",
                layer="core",
                generation_mode="template",
                prompt_excerpt="邻近模板",
                score=0.83,
            )
        ],
    )

    try:
        access_response = admin_client.post(f"/api/session/{payload['session_id']}/access")
        assert access_response.status_code == 200
        access_payload = access_response.json()
        assert access_payload["session_id"] == payload["session_id"]
        assert access_payload["session_secret"]
        assert access_payload["delete_token"]

        preview_response = admin_client.post(
            "/api/ai/rewrite-question",
            json={
                "session_id": payload["session_id"],
                "item_id": payload["question"]["template_id"],
                "style_hint": "higher-pressure scenario",
            },
        )
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert preview_payload["preview"]["template_id"] == payload["question"]["template_id"]
        assert preview_payload["preview"]["selected"]["rewritten_prompt"]
        assert len(preview_payload["preview"]["candidates"]) >= 1
        assert preview_payload["preview"]["retrieval_context"]["template_hits"][0]["object_id"] == "seed-neighbor"
    finally:
        vector_indexer.build_rewrite_retrieval_context = original


def test_admin_template_and_history_endpoints():
    create_response = admin_client.post(
        "/api/admin/item-template/create",
        json={
            "prompt": "If I could tune the question set, I would add items that reflect my own edge cases.",
            "question_type": "likert_5",
            "layer": "core",
            "dimension_weights": {"novelty_seeking": 0.6, "autonomous_judgment": 0.4},
            "subdimension_weights": {},
            "module_affinities": {},
            "discrimination": 1.35,
            "difficulty": 0.0,
            "scenario_tags": ["custom", "creator"],
            "is_anchor": False,
            "allow_rewrite": True,
            "options": [
                {"key": "strongly_disagree", "text": "Strongly disagree", "score": -1.0},
                {"key": "disagree", "text": "Disagree", "score": -0.5},
                {"key": "neutral", "text": "Neutral", "score": 0.0},
                {"key": "agree", "text": "Agree", "score": 0.5},
                {"key": "strongly_agree", "text": "Strongly agree", "score": 1.0},
            ],
        },
    )
    assert create_response.status_code == 200
    template_id = create_response.json()["item"]["id"]
    assert template_id.startswith("user-")

    invalid_response = admin_client.post(
        "/api/admin/item-template/create",
        json={
            "prompt": "People who are truly strong should dominate every relationship.",
            "question_type": "likert_5",
            "layer": "core",
            "dimension_weights": {
                "novelty_seeking": 0.5,
                "autonomous_judgment": 0.5,
                "execution_drive": 0.5,
                "planning_preference": 0.5,
            },
            "scenario_tags": ["bad"],
            "options": [
                {"key": "agree", "text": "Agree", "score": 1.0},
                {"key": "disagree", "text": "Disagree", "score": -1.0},
            ],
        },
    )
    assert invalid_response.status_code == 422

    templates_response = admin_client.get("/api/admin/templates?include_archived=true")
    assert templates_response.status_code == 200
    assert any(item["id"] == template_id for item in templates_response.json()["items"])

    sessions_response = admin_client.get("/api/admin/sessions")
    assert sessions_response.status_code == 200
    assert isinstance(sessions_response.json()["sessions"], list)

    instances_response = admin_client.get("/api/admin/item-instances")
    assert instances_response.status_code == 200
    assert isinstance(instances_response.json()["items"], list)

    cluster_response = admin_client.get("/api/admin/clusters/overview")
    assert cluster_response.status_code == 200
    assert cluster_response.json()["current_version"].startswith("kmeans-v")

    cleanup_response = admin_client.post("/api/admin/cleanup")
    assert cleanup_response.status_code == 200
    assert "removed" in cleanup_response.json()

    archive_response = admin_client.post(f"/api/admin/item-template/{template_id}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["item"]["archived"] is True

    delete_response = admin_client.delete(f"/api/admin/item-template/{template_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


def test_admin_vector_endpoints():
    template = build_seed_item_bank()[0]
    original_reindex = vector_indexer.reindex
    original_search = vector_indexer.search_similar_templates
    original_search_sessions = vector_indexer.search_similar_sessions
    original_enabled = vector_indexer.is_enabled
    original_failures = local_session_store.list_vector_sync_failures
    vector_indexer.reindex = lambda scope: VectorReindexSummary(
        scope=scope,  # type: ignore[arg-type]
        enabled=True,
        indexed_count=4,
        failed_count=1,
        failure_ids=["vf-1"],
    )
    vector_indexer.search_similar_templates = lambda **_kwargs: [
        VectorSearchHit(
            object_id="core-social-2",
            object_type="template",
            template_id="core-social-2",
            layer="core",
            generation_mode="template",
            prompt_excerpt="另一个相近模板",
            score=0.89,
        )
    ]
    vector_indexer.search_similar_sessions = lambda _session, top_k=None: [
        VectorSearchHit(
            object_id="session-snapshot-a",
            object_type="session_snapshot",
            session_id="session-similar",
            snapshot_milestone=5,
            layer="session",
            generation_mode="session_snapshot",
            prompt_excerpt="session summary",
            score=0.91,
        )
    ]
    vector_indexer.is_enabled = lambda: True
    local_session_store.list_vector_sync_failures = lambda limit=25: [
        VectorSyncFailure(
            failure_id="vf-1",
            object_type="template",
            object_id=template.id,
            operation="index_template",
            error_message="boom",
            payload_json='{"template_id":"x"}',
            created_at=datetime.now(UTC),
        )
    ]

    try:
        reindex_response = admin_client.post("/api/admin/vector/reindex", json={"scope": "sessions"})
        assert reindex_response.status_code == 200
        assert reindex_response.json()["indexed_count"] == 4

        similar_response = admin_client.get(f"/api/admin/vector/templates/similar?template_id={template.id}")
        assert similar_response.status_code == 200
        assert similar_response.json()["hits"][0]["object_id"] == "core-social-2"

        start_response = public_client.post("/api/session/start", json={"mode": "core"})
        session_id = start_response.json()["session_id"]
        session_response = admin_client.get(f"/api/admin/vector/sessions/similar?session_id={session_id}")
        assert session_response.status_code == 200
        assert session_response.json()["hits"][0]["object_type"] == "session_snapshot"

        failures_response = admin_client.get("/api/admin/vector/sync-failures")
        assert failures_response.status_code == 200
        assert failures_response.json()["items"][0]["failure_id"] == "vf-1"
    finally:
        vector_indexer.reindex = original_reindex
        vector_indexer.search_similar_templates = original_search
        vector_indexer.search_similar_sessions = original_search_sessions
        vector_indexer.is_enabled = original_enabled
        local_session_store.list_vector_sync_failures = original_failures
