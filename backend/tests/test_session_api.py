from fastapi.testclient import TestClient

from app.main import app as public_app

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


def test_public_api_does_not_expose_admin_routes():
    ai_config_response = public_client.get("/api/ai/config")
    templates_response = public_client.get("/api/admin/templates")

    assert ai_config_response.status_code == 404
    assert templates_response.status_code == 404
