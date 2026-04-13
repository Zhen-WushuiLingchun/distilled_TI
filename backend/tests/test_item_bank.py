from app.domain.item_bank import build_seed_item_bank


def test_seed_item_bank_has_core_questions():
    bank = build_seed_item_bank()
    assert len(bank) >= 90
    assert all(item.dimension_weights for item in bank)
    assert all(item.options for item in bank)
    assert any(item.layer == "sub" for item in bank)
    assert any(item.layer == "module" for item in bank)
    assert any(item.is_anchor for item in bank)
    assert any(item.allow_rewrite for item in bank)
    assert any("familiar_expression_intensity" in item.subdimension_weights for item in bank)
    assert any("low_info_decision_speed" in item.subdimension_weights for item in bank)
    assert any("switching_tendency" in item.subdimension_weights for item in bank)
    scenario_tags = {tag for item in bank for tag in item.scenario_tags}
    assert len(scenario_tags) >= 25
    assert {"open_source", "reading_group", "rpg", "fandom", "hackathon", "indie_game"} <= scenario_tags
    sub_counts: dict[str, int] = {}
    sub_scenarios: dict[str, set[tuple[str, ...]]] = {}
    for item in bank:
        for key in item.subdimension_weights:
            sub_counts[key] = sub_counts.get(key, 0) + 1
            sub_scenarios.setdefault(key, set()).add(tuple(item.scenario_tags))
    assert all(count >= 4 for count in sub_counts.values())
    assert all(len(tags) >= 4 for tags in sub_scenarios.values())
