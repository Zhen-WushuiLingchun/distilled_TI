from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

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
    vector_enabled: bool = False
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_timeout_seconds: float = 12.0
    reranker_base_url: str = ""
    reranker_api_key: str = ""
    reranker_model: str = ""
    reranker_timeout_seconds: float = 12.0
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_local_path: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_item_vectors: str = "item_vectors"
    qdrant_collection_session_vectors: str = "session_vectors"
    vector_search_top_k: int = 5
    vector_search_score_threshold: float = 0.58
    session_vector_milestones: str = "5,10,20,40"
    session_vector_top_k: int = 5
    galgame_ai_scene_enabled: bool = True
    galgame_ai_scene_timeout_seconds: float = 90.0
    galgame_ai_scene_max_tokens: int = 4096
    galgame_ai_scene_thinking_type: str = "disabled"
    galgame_ai_scene_reasoning_effort: str = ""
    galgame_ai_scene_output_effort: str = ""
    galgame_asset_generation_enabled: bool = False
    galgame_asset_backend: str = "sdwebui"
    galgame_asset_base_url: str = "http://127.0.0.1:7860"
    galgame_asset_api_key: str = ""
    galgame_asset_model: str = ""
    galgame_asset_public_dir: str = "frontend/public/generated/galgame"
    galgame_asset_public_url_prefix: str = "/generated/galgame"
    galgame_asset_timeout_seconds: float = 45.0
    galgame_asset_generate_backgrounds: bool = True
    galgame_asset_generate_characters: bool = False
    galgame_audio_asset_enabled: bool = False
    galgame_turn_vector_top_k: int = 5
    galgame_free_text_inference_min_confidence: float = 0.42
    invite_bootstrap_code: str = "DISTILLED-TI-LOCAL"
    invite_default_max_uses: int = 1000
    registered_session_ttl_days: int = 3650
    relationship_recommendations_enabled: bool = True
    # 千恋万花 人格监视器
    senren_monitor_enabled: bool = True
    senren_min_choices_for_report: int = 8


settings = Settings()
