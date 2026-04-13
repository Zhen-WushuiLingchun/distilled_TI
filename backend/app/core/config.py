from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Distilled TI Backend"
    api_prefix: str = "/api"
    session_ttl_hours: int = 1
    default_sigma: float = 1.5
    min_sigma: float = 0.35
    score_clip: float = 3.0
    eta0: float = 0.35
    eta_decay: float = 20.0
    sigma_shrink: float = 0.08
    sigma_drift: float = 0.01
    min_questions_for_report: int = 20
    max_questions_per_session: int = 10000
    subdimension_unlock_threshold: int = 4
    module_activation_threshold: int = 3
    local_db_path: str = "distilled_ti_local.db"
    ai_summary_max_tokens: int = 900
    rewrite_candidate_count: int = 4
    rewrite_target_length: int = 48
    cluster_refresh_min_samples: int = 12
    cluster_count: int = 4
    exact_repeat_cooldown: int = 36
    semantic_repeat_window: int = 24
    semantic_repeat_threshold: float = 0.58
    scenario_repeat_window: int = 6
    ranked_candidate_window: int = 40
    ai_rewrite_target_ratio: float = 0.35
    ai_rewrite_priority_bonus: float = 0.9
    ai_rewrite_expand_after_question: int = 3
    ai_probe_target_ratio: float = 0.22
    ai_probe_first_question: int = 4
    ai_probe_max_count: int = 8
    ai_contrast_target_ratio: float = 0.4


settings = Settings()
