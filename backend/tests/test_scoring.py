from app.core.config import settings
from app.domain.dimensions import MODULE_KEYS, SUBDIMENSION_TO_PARENT, make_zero_module_vector, make_zero_subdimension_vector, make_zero_vector
from app.domain.item_bank import build_seed_item_bank
from app.domain.models import AnswerRecord, SessionState
from app.services.scoring import ScoringEngine


def test_submit_response_updates_mu_and_sigma():
    state = SessionState(
        core_mu=make_zero_vector(0.0),
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0),
    )
    item = build_seed_item_bank()[0]
    engine = ScoringEngine()

    next_state = engine.apply_response(state, item, "strongly_agree")

    assert next_state.core_mu["social_initiative"] > state.core_mu["social_initiative"]
    assert next_state.core_sigma["social_initiative"] < state.core_sigma["social_initiative"]
    assert next_state.question_count == 1


def test_unlocks_subdimensions_after_threshold():
    state = SessionState(
        core_mu=make_zero_vector(0.0),
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0),
    )
    bank = {item.id: item for item in build_seed_item_bank()}
    engine = ScoringEngine()

    for item_id in ["core-social-1", "core-social-3", "cross-social-plan-1", "sub-social-entry-1"]:
        state = engine.apply_response(state, bank[item_id], "agree")

    assert "entry_speed" in state.unlocked_subdimensions
    assert state.sub_mu["entry_speed"] != 0.0
    assert state.sub_counts["entry_speed"] >= 1


def test_report_contains_sub_and_module_insights():
    state = SessionState(
        core_mu=make_zero_vector(0.0) | {"planning_preference": 0.9, "execution_drive": 0.8},
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0) | {"start_speed": 0.7, "closure_strength": 0.5},
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT} | {"start_speed": 3, "closure_strength": 2},
        module_scores=make_zero_module_vector(0.0) | {"project_role": 0.6},
        module_counts={key: 0 for key in MODULE_KEYS} | {"project_role": 2},
        dimension_counts=make_zero_vector(4),
        unlocked_subdimensions=["start_speed", "closure_strength"],
        active_modules=["project_role"],
    )
    engine = ScoringEngine()
    report = engine.build_report("session-demo", state)

    assert report.sub_insights
    assert report.module_insights
    assert report.narrative_label
    assert isinstance(report.ai_aliases, list)
    assert report.sub_insights[0].sample_count >= 1
    assert report.sub_insights[0].confidence_label
    assert report.module_insights[0].confidence_percent > 0
    assert report.cluster_mix
    assert report.cluster_mix[0].weight > 0


def test_support_risk_flags_are_non_diagnostic_operational_signals():
    state = SessionState(
        core_mu=make_zero_vector(0.0),
        core_sigma=make_zero_vector(settings.default_sigma),
        sub_mu=make_zero_subdimension_vector(0.0),
        sub_sigma=make_zero_subdimension_vector(settings.default_sigma),
        sub_counts={key: 0 for key in SUBDIMENSION_TO_PARENT},
        module_scores=make_zero_module_vector(0.0),
        module_counts={key: 0 for key in MODULE_KEYS},
        dimension_counts=make_zero_vector(0),
        zeta={"consistency": 0.2, "performative": 0.0, "exploration": 0.5, "fatigue": 0.62},
        question_count=6,
        answers=[
            AnswerRecord(
                item_id=f"item-{index}",
                template_id=f"template-{index}",
                option_key="strongly_agree",
                mapped_score=1.0,
                predicted_score=-0.6,
                residual=1.6,
                latency_ms=650,
            )
            for index in range(6)
        ],
    )
    flags = ScoringEngine().build_support_risk_flags(state)

    assert {flag.key for flag in flags} >= {
        "interaction_fatigue_or_rushing",
        "low_response_consistency",
        "high_extreme_choice_ratio",
    }
    assert all(flag.diagnostic is False for flag in flags)
    assert all(flag.suggested_action for flag in flags)
