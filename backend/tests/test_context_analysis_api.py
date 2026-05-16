from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import local_session_store


client = TestClient(app)


def test_context_analysis_flags_crisis_language_and_persists_record():
    response = client.post(
        "/api/context/analyze",
        json={
            "application_id": "chat-demo",
            "external_user_id": "user-hash-001",
            "conversation_id": "thread-001",
            "consent_basis": "demo user terms allow safety support analysis",
            "messages": [
                {"role": "assistant", "content": "我在。你现在最难受的是什么？"},
                {"role": "user", "content": "我真的不想活了，想结束生命。"},
            ],
            "persist": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] == "crisis"
    assert payload["escalation_required"] is True
    assert payload["human_review_recommended"] is True
    assert payload["diagnostic"] is False
    assert any(signal["key"] == "direct_self_harm_or_suicide_language" for signal in payload["signals"])

    records = local_session_store.list_context_analysis_records(
        application_id="chat-demo",
        external_user_id="user-hash-001",
        conversation_id="thread-001",
    )
    assert records
    assert records[-1].analysis_id == payload["analysis_id"]
    assert records[-1].response.risk_level == "crisis"

    alerts = client.get(
        "/api/context/alerts",
        params={"application_id": "chat-demo", "min_risk": "high"},
    )
    assert alerts.status_code == 200
    alert_items = alerts.json()["items"]
    assert any(item["analysis_id"] == payload["analysis_id"] for item in alert_items)


def test_context_analysis_requires_consent_basis():
    response = client.post(
        "/api/context/analyze",
        json={
            "application_id": "chat-demo",
            "external_user_id": "user-hash-002",
            "conversation_id": "thread-002",
            "consent_basis": "  ",
            "messages": [{"role": "user", "content": "今天只是有点累。"}],
        },
    )

    assert response.status_code == 422
