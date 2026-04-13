from app.core.config import settings
from app.domain.dimensions import MODULE_KEYS, SUBDIMENSION_TO_PARENT, make_zero_module_vector, make_zero_subdimension_vector, make_zero_vector
from app.domain.models import AnswerRecord, ItemInstance, QuestionOption, SessionRecord, SessionState
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.session_service import SessionService


def test_generate_probe_instance_after_probe_window():
    service = SessionService()
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {"abstraction_tendency": 0.6, "autonomous_judgment": 0.5},
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0) | {"abstraction_tendency": 3, "autonomous_judgment": 3},
        question_count=17,
    )
    session = SessionRecord(session_id="session-probe", state=state)

    instance = service._generate_probe_instance(session, None)

    assert instance is not None
    assert instance.layer == "probe"
    assert instance.generation_mode == "probe"
    assert instance.template_id.startswith("probe-")
    assert any(tag == "ai_probe" for tag in instance.scenario_tags)


def test_probe_digest_stays_compact():
    service = SessionService()
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {"abstraction_tendency": 0.6, "autonomous_judgment": 0.5},
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT} | {"academic_utility_scope": 1},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0) | {"abstraction_tendency": 3, "autonomous_judgment": 3},
        question_count=9,
        active_modules=["study_style"],
    )
    session = SessionRecord(session_id="session-probe", state=state)

    digest = service._probe_session_digest(session)

    assert "top_core_signals" in digest
    assert "highest_uncertainty_core" in digest
    assert "emerging_subdimensions" in digest
    assert "core_mu" not in digest
    assert "answers" not in digest


def test_select_next_question_avoids_semantic_near_repeat():
    service = SessionService()
    repeated = service._items["core-social-1"]
    fresh = service._items["core-risk-3"]
    service._items = {
        repeated.id: repeated,
        fresh.id: fresh,
    }
    service._instances["inst-repeat"] = ItemInstance(
        id="inst-repeat",
        template_id=repeated.id,
        session_id="session-1",
        prompt=repeated.prompt,
        question_type=repeated.question_type,
        layer=repeated.layer,
        dimension_weights=repeated.dimension_weights,
        subdimension_weights=repeated.subdimension_weights,
        module_affinities=repeated.module_affinities,
        discrimination=repeated.discrimination,
        difficulty=repeated.difficulty,
        scenario_tags=repeated.scenario_tags,
        is_anchor=repeated.is_anchor,
        allow_rewrite=repeated.allow_rewrite,
        options=repeated.options,
    )
    session = SessionRecord(
        session_id="session-1",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
            module_scores=make_zero_module_vector(0.0),
            module_counts={key: 0 for key in MODULE_KEYS},
            dimension_counts=make_zero_vector(0),
            question_count=8,
            answers=[
                AnswerRecord(
                    item_id="inst-repeat",
                    template_id=repeated.id,
                    option_key="agree",
                    mapped_score=0.5,
                    predicted_score=0.0,
                    residual=0.5,
                )
            ],
        ),
    )

    chosen = service.select_next_question(session)

    assert chosen.id == fresh.id


def test_select_next_question_prefers_unseen_templates_before_repeat():
    service = SessionService()
    seen = service._items["core-social-1"]
    unseen = service._items["core-plan-1"]
    service._items = {
        seen.id: seen,
        unseen.id: unseen,
    }
    service._instances["inst-seen"] = ItemInstance(
        id="inst-seen",
        template_id=seen.id,
        session_id="session-2",
        prompt=seen.prompt,
        question_type=seen.question_type,
        layer=seen.layer,
        dimension_weights=seen.dimension_weights,
        subdimension_weights=seen.subdimension_weights,
        module_affinities=seen.module_affinities,
        discrimination=seen.discrimination,
        difficulty=seen.difficulty,
        scenario_tags=seen.scenario_tags,
        is_anchor=seen.is_anchor,
        allow_rewrite=seen.allow_rewrite,
        options=seen.options,
    )
    session = SessionRecord(
        session_id="session-2",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
            module_scores=make_zero_module_vector(0.0),
            module_counts={key: 0 for key in MODULE_KEYS},
            dimension_counts=make_zero_vector(0),
            question_count=12,
            answers=[
                AnswerRecord(
                    item_id="inst-seen",
                    template_id=seen.id,
                    option_key="agree",
                    mapped_score=0.5,
                    predicted_score=0.0,
                    residual=0.5,
                )
            ],
        ),
    )

    chosen = service.select_next_question(session)

    assert chosen.id == unseen.id


def test_select_next_question_prefers_rewrite_templates_with_ai(monkeypatch):
    service = SessionService()
    plain = service._items["core-social-1"].model_copy(update={"allow_rewrite": False, "discrimination": 0.6})
    rewritten = service._items["core-plan-1"].model_copy(update={"allow_rewrite": True, "discrimination": 0.6})
    service._items = {
        plain.id: plain,
        rewritten.id: rewritten,
    }
    session = SessionRecord(
        session_id="session-ai",
        state=SessionState(
            core_mu=make_zero_vector(0.0),
            core_sigma=make_zero_vector(settings.default_sigma),
            sub_mu=make_zero_subdimension_vector(0.0),
            sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
            sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
            module_scores=make_zero_module_vector(0.0),
            module_counts={key: 0 for key in MODULE_KEYS},
            dimension_counts=make_zero_vector(0),
            question_count=5,
        ),
    )

    captured: dict[str, list[str]] = {}

    def _choose_first(_session, templates):
        captured["ids"] = [item.id for item in templates]
        return templates[0]

    monkeypatch.setattr("app.services.session_service.generation_service.choose_template", _choose_first)

    chosen = service.select_next_question(
        session,
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
    )

    assert chosen.id == rewritten.id

    assert captured["ids"][0] == rewritten.id


def test_generate_contrast_probe_instance(monkeypatch):
    service = SessionService()
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {"novelty_seeking": 0.7, "abstraction_tendency": 0.5},
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0) | {"novelty_seeking": 3, "abstraction_tendency": 3},
        question_count=10,
    )
    session = SessionRecord(session_id="session-contrast", state=state)

    monkeypatch.setattr(
        ai_service,
        "generate_probe_question",
        lambda **_kwargs: {
            "probe_key": "aesthetic_density",
            "probe_mode": "contrast",
            "prompt": "面对一部作品时，你的偏好更接近哪一侧？",
            "left_anchor": "多层复调、需要反复品味",
            "right_anchor": "主线清晰、表达直接明了",
            "scenario_tags": ["aesthetics"],
        },
    )

    instance = service._generate_probe_instance(session, None)

    assert instance is not None
    assert instance.question_type == "contrast_5"
    assert instance.options[0].text.startswith("明显更接近：")
    assert instance.options[-1].text.endswith("表达直接明了")


def test_fallback_probe_can_prefer_contrast(monkeypatch):
    service = SessionService()
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {"novelty_seeking": 0.7, "abstraction_tendency": 0.5},
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0) | {"novelty_seeking": 3, "abstraction_tendency": 3},
        question_count=10,
    )
    session = SessionRecord(session_id="session-contrast-fallback", state=state)

    monkeypatch.setattr(
        ai_service,
        "generate_probe_question",
        lambda **_kwargs: ai_service._fallback_probe_question(
            [
                {
                    "key": "aesthetic_density",
                    "safe_domain": "表达审美",
                    "fallback_prompt": "相比平直清爽的表达，我往往更容易被那种信息密度高、层次很多的表达吸住。",
                    "contrast_left": "多层复调、需要反复品味",
                    "contrast_right": "主线清晰、表达直接明了",
                }
            ],
            preferred_mode="contrast",
        ),
    )

    instance = service._generate_probe_instance(session, AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"))

    assert instance is not None
    assert instance.question_type == "contrast_5"
    assert "多层复调、需要反复品味" in instance.options[0].text
    assert "主线清晰、表达直接明了" in instance.options[-1].text


def test_should_generate_probe_earlier_with_ai_config():
    service = SessionService()
    state = SessionState(
        core_mu=make_zero_vector(0.0),
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0) | {"abstraction_tendency": 3, "autonomous_judgment": 3},
        question_count=4,
    )
    session = SessionRecord(session_id="session-early-probe", state=state)

    enabled = service._should_generate_probe(
        session,
        AIProviderConfig(provider="x", model="y", base_url="https://example.com", api_key="z"),
    )

    assert enabled is True
