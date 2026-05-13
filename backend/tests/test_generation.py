from app.core.config import settings
from app.domain.item_bank import build_seed_item_bank
from app.domain.models import AnswerRecord, SessionRecord, SessionState
from app.domain.dimensions import make_zero_module_vector, make_zero_subdimension_vector, make_zero_vector
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.generation import generation_service
from app.services.validators import validate_contrast_probe, validate_likert_prompt


def test_generation_creates_instance_from_template():
    template = build_seed_item_bank()[0]
    session = SessionRecord(
        session_id="session-test",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )

    instance, preview = generation_service.materialize_instance(session, template, "更高压的项目语境")

    assert instance.template_id == template.id
    assert instance.id.startswith("inst-")
    assert preview.selected.rewritten_prompt
    assert len(preview.candidates) >= 1
    assert preview.selected.rewritten_prompt == template.prompt
    assert preview.selected.score >= preview.candidates[-1].score


def test_generation_candidate_dedup_filters_semantic_near_duplicates():
    deduped = generation_service._dedupe_candidates(
        "template-1",
        [
            {"rewritten_prompt": "当真实代价落下时，我会先把推进节奏定出来。", "generation_mode": "template", "validator_passed": True},
            {"rewritten_prompt": "当真实代价真正落下时，我会先把推进节奏定出来。", "generation_mode": "template", "validator_passed": True},
            {"rewritten_prompt": "面对高压项目时，我通常先搭出执行骨架。", "generation_mode": "template", "validator_passed": True},
        ],
    )
    assert len(deduped) == 2


def test_fallback_candidates_do_not_leak_style_hint_literal():
    template = build_seed_item_bank()[0]
    candidates = ai_service.rewrite_template_candidates(
        "session-test",
        template,
        "高辨识度、场景更具体、语气稍微更有压强",
        4,
    )
    prompts = [str(item["rewritten_prompt"]) for item in candidates]
    assert all("高辨识度、场景更具体、语气稍微更有压强" not in prompt for prompt in prompts)


def test_choose_template_skips_recent_template_ids():
    templates = build_seed_item_bank()[:3]
    session = SessionRecord(
        session_id="session-test",
        current_template_id=templates[0].id,
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            recent_item_ids=[templates[0].id],
            answers=[
                AnswerRecord(
                    item_id="inst-1",
                    template_id=templates[0].id,
                    option_key="agree",
                    mapped_score=0.5,
                    predicted_score=0.0,
                    residual=0.5,
                )
            ],
            dimension_counts=make_zero_vector(0),
        ),
    )

    chosen = generation_service.choose_template(session, templates)

    assert chosen.id != templates[0].id


def test_materialize_instance_skips_llm_rewrite_for_non_rewrite_template(monkeypatch):
    template = build_seed_item_bank()[0]
    assert template.allow_rewrite is False
    session = SessionRecord(
        session_id="session-test",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )

    def _raise_if_called(*_args, **_kwargs):
        raise AssertionError("rewrite_template_candidates should not be called for non-rewrite templates")

    monkeypatch.setattr(ai_service, "rewrite_template_candidates", _raise_if_called)

    instance, preview = generation_service.materialize_instance(
        session,
        template,
        "更高压的项目语境",
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
    )

    assert instance.generation_mode == "template"
    assert preview.selected.rewritten_prompt


def test_materialize_instance_uses_llm_rewrite_for_plain_template_after_expand_threshold(monkeypatch):
    template = build_seed_item_bank()[0]
    assert template.allow_rewrite is False
    session = SessionRecord(
        session_id="session-test",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
            question_count=settings.ai_rewrite_expand_after_question,
        ),
    )

    monkeypatch.setattr(
        ai_service,
        "rewrite_template_candidates",
        lambda *_args, **_kwargs: [
            {
                "rewritten_prompt": "真实局面压上来时，我通常还能把要处理的事和情绪先分开。",
                "generation_mode": "llm_rewrite",
                "validator_passed": True,
            }
        ],
    )

    instance, preview = generation_service.materialize_instance(
        session,
        template,
        "更高压的项目语境",
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
    )

    assert instance.generation_mode == "llm_rewrite"
    assert preview.selected.rewritten_prompt != template.prompt


def test_rewrite_template_candidates_fallback_to_original_prompt_on_ai_failure(monkeypatch):
    template = build_seed_item_bank()[0]

    def _raise(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.Client.post", _raise)

    candidates = ai_service.rewrite_template_candidates(
        "session-test",
        template,
        "高辨识度、场景更具体、语气稍微更有压强",
        4,
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
    )

    assert len(candidates) == 1
    assert candidates[0]["rewritten_prompt"] == template.prompt


def test_parse_json_object_accepts_fenced_json():
    parsed = ai_service._parse_json_object(
        """```json
        {"narrative_label":"会拐弯的扳手","ai_aliases":["过热规划器"],"ai_summary":"你不是没动力，你是总想先把轨道修到自己满意。"}
        ```"""
    )

    assert parsed["narrative_label"] == "会拐弯的扳手"
    assert parsed["ai_aliases"] == ["过热规划器"]


def test_galgame_scene_request_adds_deepseek_thinking_control(monkeypatch):
    monkeypatch.setattr(settings, "galgame_ai_scene_thinking_type", "disabled")
    monkeypatch.setattr(settings, "galgame_ai_scene_reasoning_effort", "")
    monkeypatch.setattr(settings, "galgame_ai_scene_output_effort", "")

    request_json = {"model": "deepseek-v4-pro", "messages": []}
    ai_service._apply_galgame_scene_provider_controls(
        request_json,
        AIProviderConfig(provider="deepseek", model="deepseek-v4-pro", base_url="https://api.deepseek.com", api_key="x"),
    )

    assert request_json["thinking"] == {"type": "disabled"}


def test_galgame_scene_request_variants_drop_optional_provider_controls():
    request_json = {
        "model": "deepseek-v4-pro",
        "messages": [],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "reasoning_effort": "high",
        "output_config": {"effort": "high"},
    }

    variants = ai_service._galgame_scene_request_variants(request_json)

    assert variants[0]["thinking"] == {"type": "disabled"}
    assert any("response_format" not in variant and "thinking" in variant for variant in variants)
    assert any("thinking" not in variant and "response_format" in variant for variant in variants)
    assert any("thinking" not in variant and "response_format" not in variant for variant in variants)


def test_galgame_choice_texts_accept_dict_or_list_shapes():
    option_keys = {"agree", "neutral"}

    from_dict = ai_service._normalize_galgame_choice_texts(
        {"agree": "接过钥匙。", "other": "忽略。"},
        option_keys,
    )
    from_list = ai_service._normalize_galgame_choice_texts(
        [
            {"option_key": "agree", "text": "接过钥匙。"},
            {"key": "neutral", "value": "先等一等。"},
            {"option_key": "other", "text": "忽略。"},
        ],
        option_keys,
    )

    assert from_dict == {"agree": "接过钥匙。"}
    assert from_list == {"agree": "接过钥匙。", "neutral": "先等一等。"}


def test_preview_rewrite_without_ai_returns_original_template_prompt():
    template = build_seed_item_bank()[0]
    session = SessionRecord(
        session_id="session-no-ai",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )

    preview = generation_service.preview_rewrite(session, template, "高辨识度、场景更具体、语气稍微更有压强", None)

    assert preview.selected.rewritten_prompt == template.prompt
    assert preview.selected.generation_mode == "template"


def test_fallback_candidates_use_seeded_diverse_frames():
    prompt = "我通常会先把局面推进成一个可执行的起点。"
    left = ai_service.fallback_template_candidates(prompt, None, 4, seed_key="session-a:item-1:3")
    right = ai_service.fallback_template_candidates(prompt, None, 4, seed_key="session-b:item-1:3")

    left_prompts = [str(item["rewritten_prompt"]) for item in left]
    right_prompts = [str(item["rewritten_prompt"]) for item in right]

    assert left_prompts != right_prompts
    assert all("当一桌人都在互相等别人先动时" not in text for text in left_prompts + right_prompts)


def test_validate_likert_prompt_rejects_forced_choice_question():
    errors = validate_likert_prompt("在欣赏一部电影或阅读一本书时，你通常更享受需要反复品味的作品，还是更偏爱表达直接明了的作品？")

    assert errors
    assert any("同意/不同意" in error or "同意量表" in error for error in errors)


def test_validate_contrast_probe_accepts_anchor_based_question():
    errors = validate_contrast_probe(
        "面对一部作品时，你的偏好更接近哪一侧？",
        "多层复调、需要反复品味",
        "主线清晰、表达直接明了",
    )

    assert errors == []


def test_choose_template_randomizes_by_session_seed():
    templates = build_seed_item_bank()[:8]
    session_a = SessionRecord(
        session_id="session-a",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )
    session_b = SessionRecord(
        session_id="session-b",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(1.5),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(1.5),
            module_scores=make_zero_module_vector(0.0),
            dimension_counts=make_zero_vector(0),
        ),
    )

    chosen_a = generation_service.choose_template(session_a, templates)
    chosen_b = generation_service.choose_template(session_b, templates)

    assert chosen_a.id in {item.id for item in templates[:8]}
    assert chosen_b.id in {item.id for item in templates[:8]}
