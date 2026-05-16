from fastapi.testclient import TestClient

from app.core.config import settings
from app.domain.models import VectorSearchHit
from app.main import app as public_app
from app.services.ai_service import ai_service
from app.services.storage import local_session_store
from app.services.user_service import user_service
from app.services.vector_indexer import vector_indexer

public_client = TestClient(public_app)


def create_test_invite(max_uses: int = 1) -> str:
    return user_service.create_invite(label="test invite", max_uses=max_uses).code


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
    assert local_session_store.load_session(payload["session_id"]).mode == "core"
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


def test_story_session_mode_is_preserved_in_history():
    start_response = public_client.post("/api/session/start", json={"mode": "story"})
    assert start_response.status_code == 200
    payload = start_response.json()

    record = local_session_store.load_session(payload["session_id"])
    assert record is not None
    assert record.mode == "story"

    history = local_session_store.list_sessions()
    entry = next(item for item in history if item.session_id == payload["session_id"])
    assert entry.mode == "story"


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
    invite_code = create_test_invite()
    redeem_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": invite_code, "email": "history-user@example.com"},
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
    assert profile_response.json()["email_registered"] is True
    assert "user_secret_hash" not in profile_response.json()

    start_response = public_client.post("/api/session/start", json={"mode": "core"}, headers=user_headers)
    assert start_response.status_code == 200
    session_payload = start_response.json()

    sessions_response = public_client.get("/api/user/sessions", headers=user_headers)
    assert sessions_response.status_code == 200
    sessions_payload = sessions_response.json()
    assert sessions_payload["user"]["handle"] == user_access["handle"]
    assert any(item["session_id"] == session_payload["session_id"] for item in sessions_payload["sessions"])

    evolution_response = public_client.get("/api/user/evolution", headers=user_headers)
    assert evolution_response.status_code == 200
    assert any(item["session_id"] == session_payload["session_id"] for item in evolution_response.json()["items"])

    recommendations_response = public_client.get("/api/user/recommendations", headers=user_headers)
    assert recommendations_response.status_code == 200
    assert "enabled" in recommendations_response.json()
    assert isinstance(recommendations_response.json()["items"], list)

    access_response = public_client.post(
        f"/api/user/session/{session_payload['session_id']}/access",
        json={},
        headers=user_headers,
    )
    assert access_response.status_code == 200
    assert access_response.json()["session_secret"]


def test_share_invite_belongs_to_sharer_and_can_be_claimed_by_existing_user():
    inviter_signup_code = create_test_invite()
    inviter_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": inviter_signup_code, "email": "inviter@example.com"},
    )
    assert inviter_response.status_code == 200
    inviter = inviter_response.json()
    inviter_headers = {
        "X-User-Id": inviter["user_id"],
        "X-User-Secret": inviter["user_secret"],
    }
    inviter_profile_response = public_client.get("/api/user/me", headers=inviter_headers)
    assert inviter_profile_response.status_code == 200
    inviter_profile = inviter_profile_response.json()
    share_invite = local_session_store.load_invite_code(inviter_profile["invite_code"])
    assert share_invite is not None
    assert share_invite.created_by_user_id == inviter["user_id"]
    assert share_invite.max_uses == 1

    new_user_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": inviter_profile["invite_code"], "email": "invited-new@example.com"},
    )
    assert new_user_response.status_code == 200
    used_share_invite = local_session_store.load_invite_code(inviter_profile["invite_code"])
    assert used_share_invite is not None
    assert used_share_invite.active is False
    spent_profile_response = public_client.get("/api/user/me", headers=inviter_headers)
    assert spent_profile_response.status_code == 200
    assert spent_profile_response.json()["invite_code"] is None
    assert spent_profile_response.json()["invite_available"] is False
    new_user = new_user_response.json()
    new_user_relationships = local_session_store.list_user_relationships(user_id=new_user["user_id"], limit=100)
    assert any(
        relationship.source_user_id == inviter["user_id"]
        and relationship.target_user_id == new_user["user_id"]
        for relationship in new_user_relationships
    )

    next_invite_response = public_client.post("/api/user/invite/generate", json={}, headers=inviter_headers)
    assert next_invite_response.status_code == 200
    next_invite = next_invite_response.json()["invite_code"]
    assert next_invite and next_invite != inviter_profile["invite_code"]

    existing_signup_code = create_test_invite()
    existing_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": existing_signup_code, "email": "existing-claimant@example.com"},
    )
    assert existing_response.status_code == 200
    existing = existing_response.json()
    existing_headers = {
        "X-User-Id": existing["user_id"],
        "X-User-Secret": existing["user_secret"],
    }

    claim_response = public_client.post(
        "/api/user/invite/claim",
        json={"invite_code": next_invite},
        headers=existing_headers,
    )
    assert claim_response.status_code == 200
    relationships = local_session_store.list_user_relationships(user_id=existing["user_id"], limit=100)
    assert any(
        relationship.source_user_id == inviter["user_id"]
        and relationship.target_user_id == existing["user_id"]
        for relationship in relationships
    )


def test_invite_registration_requires_unique_email():
    invite_code = create_test_invite(max_uses=2)
    first_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": invite_code, "email": "Unique.User@example.com"},
    )
    assert first_response.status_code == 200

    duplicate_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": invite_code, "email": "unique.user@example.com"},
    )
    assert duplicate_response.status_code == 422
    assert duplicate_response.json()["detail"] == "email_already_registered"

    invalid_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": invite_code, "email": "not-an-email"},
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["detail"] == "invalid_email"


def test_galgame_scene_wraps_current_question_and_records_custom_text(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_service, "generate_galgame_scene", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(settings, "galgame_asset_public_dir", str(tmp_path / "generated"))
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    payload = start_response.json()
    headers = session_headers(payload["session_secret"])

    scene_response = public_client.get(
        f"/api/session/{payload['session_id']}/galgame/scene",
        headers=headers,
    )
    assert scene_response.status_code == 200
    scene = scene_response.json()
    assert scene["item_id"] == payload["question"]["id"]
    assert scene["choices"]
    assert scene["custom_input_enabled"] is True
    assert scene["background_key"]
    assert scene["character_key"]
    assert scene["background_asset"]["url"].startswith("/galgame-assets/backgrounds/")
    assert scene["character_asset"]["url"].startswith("/galgame-assets/sprites/")
    assert scene["ai_generated"] is False
    assert scene["prompt_shadow"] == "hidden_measurement_seed"
    visible_scene_text = "\n".join(
        [
            scene["narrator_text"],
            scene["character_text"],
            *[choice["text"] for choice in scene["choices"]],
        ]
    )
    assert payload["question"]["prompt"] not in visible_scene_text
    assert "非常同意" not in visible_scene_text
    assert "非常不同意" not in visible_scene_text
    assert "当前映射" not in visible_scene_text

    response = public_client.post(
        f"/api/session/{payload['session_id']}/galgame/respond",
        json={
            "item_id": scene["item_id"],
            "scene_id": scene["scene_id"],
            "option_key": scene["choices"][0]["option_key"],
            "choice_text": scene["choices"][0]["text"],
            "custom_text": "我先观察一下对方真正担心什么，再决定要不要推进。",
            "latency_ms": 1800,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["question_count"] == 1
    assert body["text_inference"]["source"] in {"rule", "embedding", "pairwise", "llm", "hybrid"}
    assert "pairwise_available" in body["text_inference"]
    assert isinstance(body["text_inference"]["option_scores"], list)
    if body["text_inference"]["inferred_option_key"] and body["text_inference"]["confidence"] >= 0.42:
        assert body["state"]["answers"][-1]["option_key"] == body["text_inference"]["inferred_option_key"]
    assert body["scene"]["item_id"] != scene["item_id"]
    assert body["scene"]["memory_fragments"]
    turns = local_session_store.list_galgame_turns(payload["session_id"], limit=1)
    assert turns[-1].scene_text == "我先观察一下对方真正担心什么，再决定要不要推进。"

    stale_response = public_client.post(
        f"/api/session/{payload['session_id']}/galgame/respond",
        json={
            "item_id": scene["item_id"],
            "scene_id": scene["scene_id"],
            "option_key": scene["choices"][0]["option_key"],
        },
        headers=headers,
    )
    assert stale_response.status_code == 404


def test_galgame_scene_filters_ai_measurement_leaks(monkeypatch, tmp_path):
    def fake_scene(scene_payload):
        first_choice = scene_payload["choices"][0]
        second_choice = scene_payload["choices"][1]
        return {
            "title": "量表场景",
            "location": "心理测试室",
            "mood": "测量",
            "speaker": "option_key",
            "narrator_text": scene_payload["private_analysis_seed"]["layer"],
            "character_text": f"请回答：{first_choice['text']}",
            "choice_texts": {
                first_choice["option_key"]: "非常同意 +1.00",
                second_choice["option_key"]: "不同意 -0.50",
            },
            "background_key": "bad_background",
            "background_prompt": "classroom background, no humans, no text",
            "character_key": "bad_character",
            "character_prompt": "visual novel portrait",
        }

    monkeypatch.setattr(ai_service, "generate_galgame_scene", fake_scene)
    monkeypatch.setattr(settings, "galgame_asset_public_dir", str(tmp_path / "generated"))
    start_response = public_client.post("/api/session/start", json={"mode": "core"})
    payload = start_response.json()

    scene_response = public_client.get(
        f"/api/session/{payload['session_id']}/galgame/scene",
        headers=session_headers(payload["session_secret"]),
    )

    assert scene_response.status_code == 200
    scene = scene_response.json()
    visible_scene_text = "\n".join(
        [
            scene["title"],
            scene["location"],
            scene["mood"],
            scene["speaker"],
            scene["narrator_text"],
            scene["character_text"],
            *[choice["text"] for choice in scene["choices"]],
        ]
    )
    assert payload["question"]["prompt"] not in visible_scene_text
    assert "非常同意" not in visible_scene_text
    assert "不同意" not in visible_scene_text
    assert "心理测试" not in visible_scene_text
    assert "option_key" not in visible_scene_text
    assert "测量" not in visible_scene_text


def test_invite_user_can_manage_private_galgame_story_templates(monkeypatch):
    monkeypatch.setattr(ai_service, "generate_galgame_scene", lambda *_args, **_kwargs: None)
    invite_code = create_test_invite()
    redeem_response = public_client.post(
        "/api/invite/redeem",
        json={"invite_code": invite_code, "email": "story-template-owner@example.com"},
    )
    assert redeem_response.status_code == 200
    user_access = redeem_response.json()
    user_headers = {
        "X-User-Id": user_access["user_id"],
        "X-User-Secret": user_access["user_secret"],
    }

    create_response = public_client.post(
        "/api/user/galgame/story-templates",
        headers=user_headers,
        json={
            "name": "公开入口自定义社团夜谈",
            "description": "玩家自定义的校园夜谈模板。",
            "location": "只在本人账号出现的天台温室",
            "speaker": "温室值夜员",
            "character_key": "private_keeper",
            "background_key": "private_rooftop_greenhouse",
            "background_prompt": "rooftop greenhouse at night",
            "character_prompt": "quiet greenhouse keeper",
            "style_prompt": "更像轻小说分支，不像问卷。",
            "scenario_tags": ["relationship", "team_mode", "campus"],
            "active": True,
        },
    )
    assert create_response.status_code == 200
    template = create_response.json()
    assert template["template_id"].startswith(f"user-story-{user_access['user_id'][:8]}-")
    assert template["owner_user_id"] == user_access["user_id"]

    list_response = public_client.get("/api/user/galgame/story-templates", headers=user_headers)
    assert list_response.status_code == 200
    assert any(item["template_id"] == template["template_id"] for item in list_response.json()["items"])

    update_response = public_client.put(
        f"/api/user/galgame/story-templates/{template['template_id']}",
        headers=user_headers,
        json={
            "name": "公开入口自定义社团夜谈改",
            "description": "玩家自定义的校园夜谈模板。",
            "location": "只在本人账号出现的天台温室",
            "speaker": "温室值夜员",
            "character_key": "private_keeper",
            "background_key": "private_rooftop_greenhouse",
            "background_prompt": "rooftop greenhouse at night",
            "character_prompt": "quiet greenhouse keeper",
            "style_prompt": "更像轻小说分支，不像问卷。",
            "scenario_tags": ["relationship", "team_mode", "campus"],
            "active": True,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"].endswith("改")

    start_response = public_client.post("/api/session/start", json={"mode": "core"}, headers=user_headers)
    assert start_response.status_code == 200
    session_payload = start_response.json()
    scene_response = public_client.get(
        f"/api/session/{session_payload['session_id']}/galgame/scene",
        headers=session_headers(session_payload["session_secret"]),
    )
    assert scene_response.status_code == 200
    scene = scene_response.json()
    assert scene["story_template_id"]

    delete_response = public_client.delete(
        f"/api/user/galgame/story-templates/{template['template_id']}",
        headers=user_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True


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
