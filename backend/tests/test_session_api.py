from fastapi.testclient import TestClient

from app.domain.models import VectorSearchHit
from app.main import app as public_app
from app.services.vector_indexer import vector_indexer

public_client = TestClient(public_app)


def session_headers(session_secret: str) -> dict[str, str]:
    return {"X-Session-Secret": session_secret}


def delete_headers(delete_token: str) -> dict[str, str]:
    return {"X-Delete-Token": delete_token}


def choose_option_key(question: dict) -> str:
    option_keys = [option["key"] for option in question["options"]]
    for preferred in ("agree", "right", "strongly_agree", "strongly_right", "neutral"):
        if preferred in option_keys:
            return preferred
    return option_keys[-1]


def advance_questions(access: dict[str, str], first_question: dict, count: int) -> dict:
    current_question = first_question
    last_payload: dict = {}
    headers = session_headers(access["session_secret"])
    for _ in range(count):
        response = public_client.post(
            "/api/response/submit",
            json={
                "session_id": access["session_id"],
                "item_id": current_question["id"],
                "option_key": choose_option_key(current_question),
                "latency_ms": 2200,
            },
            headers=headers,
        )
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["next_question"] is None:
            break
        current_question = last_payload["next_question"]
    return last_payload


def test_public_session_flow_requires_tokens_and_supports_resume():
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    assert start_response.status_code == 200
    payload = start_response.json()

    assert payload["session_id"]
    assert payload["session_secret"]
    assert payload["delete_token"]
    assert payload["question"]["id"]
    assert payload["question"]["template_id"]
    assert payload["min_questions_for_report"] == 20
    assert payload["workbench_checkpoint"]["question_count"] == 0
    assert payload["workbench_checkpoint"]["report_ready"] is False
    assert payload["workbench_checkpoint"]["milestones"][0]["milestone"] == 5

    summary_without_token = public_client.get(f"/api/session/{payload['session_id']}/summary")
    assert summary_without_token.status_code == 401

    summary_response = public_client.get(
        f"/api/session/{payload['session_id']}/summary",
        headers=session_headers(payload["session_secret"]),
    )
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["can_generate_report"] is False
    assert summary_payload["current_question"]["id"] == payload["question"]["id"]
    assert summary_payload["workbench_checkpoint"]["remaining_until_report"] == 20
    assert summary_payload["workbench_checkpoint"]["uncertainty_queue"]

    early_report_response = public_client.get(
        f"/api/session/{payload['session_id']}/report",
        headers=session_headers(payload["session_secret"]),
    )
    assert early_report_response.status_code == 409

    submit_payload = advance_questions(payload, payload["question"], 20)
    assert submit_payload["state"]["question_count"] >= 20
    assert submit_payload["can_generate_report"] is True
    assert submit_payload["workbench_checkpoint"]["report_ready"] is True
    assert submit_payload["workbench_checkpoint"]["report_progress_percent"] == 100

    report_response = public_client.get(
        f"/api/session/{payload['session_id']}/report",
        headers=session_headers(payload["session_secret"]),
    )
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert report_payload["session_id"] == payload["session_id"]
    assert report_payload["can_exit_with_report"] is True
    assert report_payload["ai_summary"]
    assert report_payload["narrative_label"]
    assert report_payload["core_bars"]
    assert "cluster_confidence" in report_payload
    assert "cluster_mix" in report_payload
    assert "ai_aliases" in report_payload
    assert "salient_subdimensions" in report_payload
    assert "sub_insights" in report_payload
    assert "module_insights" in report_payload
    assert len(report_payload["cluster_mix"]) >= 1

    map_response = public_client.get(
        f"/api/session/{payload['session_id']}/map",
        headers=session_headers(payload["session_secret"]),
    )
    assert map_response.status_code == 200
    map_payload = map_response.json()
    assert "confidence" in map_payload
    assert "answer_points" in map_payload
    assert "trajectory_points" in map_payload
    assert "cluster_centers" in map_payload
    assert "cluster_regions" in map_payload

    delete_without_token = public_client.delete(f"/api/session/{payload['session_id']}")
    assert delete_without_token.status_code == 401

    delete_response = public_client.delete(
        f"/api/session/{payload['session_id']}",
        headers=delete_headers(payload["delete_token"]),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True

    missing_response = public_client.get(
        f"/api/session/{payload['session_id']}/summary",
        headers=session_headers(payload["session_secret"]),
    )
    assert missing_response.status_code == 404


def test_session_secret_is_bound_to_owner_fingerprint():
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    payload = start_response.json()

    other_client = TestClient(public_app, headers={"user-agent": "different-browser"})
    response = other_client.get(
        f"/api/session/{payload['session_id']}/summary",
        headers=session_headers(payload["session_secret"]),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "session_owner_mismatch"


def test_invite_user_can_keep_long_lived_session_history():
    redeem_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": "DISTILLED-TI-LOCAL"},
    )
    assert redeem_response.status_code == 200
    user_access = redeem_response.json()
    assert user_access["user_id"]
    assert user_access["user_secret"]
    assert user_access["handle"]

    user_headers = {
        "X-User-Id": user_access["user_id"],
        "X-User-Secret": user_access["user_secret"],
    }
    profile_response = public_client.get("/api/user/me", headers=user_headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["handle"] == user_access["handle"]
    assert "user_secret_hash" not in profile_response.json()

    start_response = public_client.post("/api/session/start", json={"mode": "core"}, headers=user_headers)
    assert start_response.status_code == 200
    session_payload = start_response.json()

    sessions_response = public_client.get("/api/user/sessions", headers=user_headers)
    assert sessions_response.status_code == 200
    sessions_payload = sessions_response.json()
    assert sessions_payload["user"]["handle"] == user_access["handle"]
    assert any(item["session_id"] == session_payload["session_id"] for item in sessions_payload["sessions"])

    access_response = public_client.post(
        f"/api/user/session/{session_payload['session_id']}/access",
        json={},
        headers=user_headers,
    )
    assert access_response.status_code == 200
    assert access_response.json()["session_secret"]


def test_workbench_evidence_requires_secret_and_hides_raw_scores(monkeypatch):
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    payload = start_response.json()

    no_token_response = public_client.get(f"/api/session/{payload['session_id']}/workbench/evidence")
    assert no_token_response.status_code == 401

    monkeypatch.setattr(vector_indexer, "is_enabled", lambda: True)
    monkeypatch.setattr(vector_indexer, "build_rewrite_retrieval_context", lambda _template: None)
    monkeypatch.setattr(
        vector_indexer,
        "search_similar_templates",
        lambda **_kwargs: [
            VectorSearchHit(
                object_id="template-neighbor-1",
                object_type="template",
                template_id="template-neighbor-1",
                layer="core",
                generation_mode="template",
                prompt_excerpt="A nearby template prompt",
                score=0.93,
                rerank_score=0.81,
                scenario_tags=["study"],
            )
        ],
    )
    monkeypatch.setattr(
        vector_indexer,
        "search_similar_sessions",
        lambda _session, top_k=None: [
            VectorSearchHit(
                object_id="session-neighbor-1:5",
                object_type="session_snapshot",
                session_id="session-neighbor-1",
                snapshot_milestone=5,
                layer="session",
                generation_mode="snapshot",
                prompt_excerpt="session_id=hidden",
                score=0.89,
                rerank_score=None,
            )
        ],
    )

    response = public_client.get(
        f"/api/session/{payload['session_id']}/workbench/evidence",
        headers=session_headers(payload["session_secret"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["vector_available"] is True
    assert body["reranker_applied"] is True
    assert body["item_evidence"][0]["confidence_tier"] == "high"
    assert body["item_evidence"][0]["reference_key"].startswith("template:")
    assert body["session_evidence"][0]["prompt_excerpt"] != "session_id=hidden"

    def assert_no_raw_scores(value):
        if isinstance(value, dict):
            assert "score" not in value
            assert "rerank_score" not in value
            for nested in value.values():
                assert_no_raw_scores(nested)
        elif isinstance(value, list):
            for nested in value:
                assert_no_raw_scores(nested)

    assert_no_raw_scores(body)


def test_public_api_does_not_expose_admin_routes():
    ai_config_response = public_client.get("/api/ai/config")
    templates_response = public_client.get("/api/admin/templates")

    assert ai_config_response.status_code == 404
    assert templates_response.status_code == 404
