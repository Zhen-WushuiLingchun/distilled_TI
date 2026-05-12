"""Configurable AI provider helpers with persistent local config."""

from __future__ import annotations

import json
import math
import random
import re
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import GalgameChoice, GalgameOptionTendency, GalgameTextInference, ItemTemplate
from app.services.embedding_service import EmbeddingServiceError, embedding_service
from app.services.storage import local_session_store
from app.services.validators import validate_contrast_probe, validate_generated_prompt, validate_likert_prompt


class AIProviderConfig(BaseModel):
    provider: str
    model: str
    base_url: str
    api_key: str


class AIService:
    def __init__(self) -> None:
        self._config: AIProviderConfig | None = None

    def configure(self, provider: str, model: str, base_url: str, api_key: str) -> AIProviderConfig:
        config = AIProviderConfig(
            provider=provider,
            model=model,
            base_url=base_url.rstrip("/"),
            api_key=api_key,
        )
        self._config = config
        local_session_store.save_ai_provider_config(config.model_dump_json())
        return config

    def _resolve_config(self, runtime_config: AIProviderConfig | None = None) -> AIProviderConfig | None:
        if runtime_config is not None:
            return runtime_config

        payload_json = local_session_store.load_ai_provider_config()
        if payload_json is None:
            self._config = None
            return None

        if self._config is not None and self._config.model_dump_json() == payload_json:
            return self._config

        self._config = AIProviderConfig.model_validate_json(payload_json)
        return self._config

    def get_config(self) -> AIProviderConfig | None:
        return self._resolve_config()

    def has_config(self) -> bool:
        return self._resolve_config() is not None

    def get_public_config(self) -> dict[str, str | bool] | None:
        active_config = self._resolve_config()
        if active_config is None:
            return None
        return {
            "provider": active_config.provider,
            "model": active_config.model,
            "base_url": active_config.base_url,
            "configured": True,
        }

    def test_config(self, config: AIProviderConfig) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                response = client.post(
                    f"{config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": config.model,
                        "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
                        "temperature": 0,
                        "max_tokens": 128,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = str(data["choices"][0]["message"]["content"]).strip().lower()
                if not content:
                    return False, "AI 服务返回空响应。"
                return True, "AI 连接测试通过。"
        except Exception as exc:  # pragma: no cover - exercised by tests via fallback paths
            return False, f"AI 连接测试失败：{exc}"

    def rewrite_question(self, item_id: str, style_hint: str | None = None) -> str:
        active_config = self._resolve_config()
        if active_config is None:
            return "AI provider 尚未配置，当前仅保留了题目改写接口。"
        if style_hint:
            return f"已预留题目改写能力，后续将使用 {active_config.provider}/{active_config.model} 按风格 {style_hint} 改写题目 {item_id}。"
        return f"已预留题目改写能力，后续将使用 {active_config.provider}/{active_config.model} 改写题目 {item_id}。"

    def rewrite_template_candidates(
        self,
        session_id: str,
        template: ItemTemplate,
        style_hint: str | None = None,
        candidate_count: int | None = None,
        runtime_ai_config: AIProviderConfig | None = None,
        retrieval_context: dict[str, object] | None = None,
    ) -> list[dict[str, object]]:
        fallback_candidates = [
            {
                "rewritten_prompt": template.prompt,
                "generation_mode": "template",
                "validator_passed": True,
            }
        ]
        desired_count = candidate_count or settings.rewrite_candidate_count
        active_config = self._resolve_config(runtime_ai_config)
        if active_config is None:
            return fallback_candidates

        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.post(
                    f"{active_config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_config.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "你是 Distilled TI 的题目改写器。"
                                    "只重写措辞，不改变测量方向、选项数量和回答结构。"
                                    "不要复制近邻题目的表述，不要偏移原始维度与场景。"
                                    "输出纯 JSON："
                                    '{"candidates":[{"rewritten_prompt":"..."}]}'
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "session_id": session_id,
                                        "style_hint": style_hint,
                                        "template_id": template.id,
                                        "layer": template.layer,
                                        "scenario_tags": template.scenario_tags,
                                        "dimension_weights": template.dimension_weights,
                                        "subdimension_weights": template.subdimension_weights,
                                        "prompt": template.prompt,
                                        "retrieval_context": retrieval_context or {},
                                        "constraints": {
                                            "non_moralizing": True,
                                            "no_sensitive_topics": True,
                                            "keep_measurement_direction": True,
                                            "avoid_copying_near_neighbors": True,
                                            "length_limit": 160,
                                            "candidate_count": desired_count,
                                        },
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        ],
                        "temperature": 0.7,
                        "max_tokens": 260,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = str(data["choices"][0]["message"]["content"]).strip()
                parsed = self._parse_json_object(content)
                candidates = parsed.get("candidates", [])
                normalized: list[dict[str, object]] = []
                for candidate in candidates:
                    prompt = str(candidate.get("rewritten_prompt", "")).strip()
                    if not prompt:
                        continue
                    normalized.append(
                        {
                            "rewritten_prompt": prompt,
                            "generation_mode": "llm_rewrite",
                            "validator_passed": len(validate_generated_prompt(prompt)) == 0,
                        }
                    )
                return normalized or fallback_candidates
        except Exception:
            return fallback_candidates

    def fallback_template_candidates(
        self,
        prompt: str,
        style_hint: str | None = None,
        candidate_count: int | None = None,
        seed_key: str | None = None,
    ) -> list[dict[str, object]]:
        desired_count = candidate_count or settings.rewrite_candidate_count
        return self._fallback_candidates(prompt, style_hint, desired_count, seed_key=seed_key)

    def summarize_report(self, report_payload: dict[str, object]) -> str:
        return self.summarize_report_with_config(report_payload, None)

    def interpret_report_with_config(
        self,
        report_payload: dict[str, object],
        runtime_config: AIProviderConfig | None,
        naming_style: str | None = None,
    ) -> dict[str, object]:
        active_config = self._resolve_config(runtime_config)
        fallback = {
            "narrative_label": str(report_payload.get("narrative_label", "未命名结构体")),
            "ai_aliases": [],
            "ai_summary": self._fallback_summary(report_payload),
        }
        if active_config is None:
            return fallback

        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.post(
                    f"{active_config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_config.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "你是 Distilled TI 的命名与总结器。"
                                    "基于结构化数据输出更有辨识度的中文命名和摘要。"
                                    "输出纯 JSON："
                                    '{"narrative_label":"...","ai_aliases":["..."],"ai_summary":"..."}'
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {"naming_style": naming_style or "auto", "report": report_payload},
                                    ensure_ascii=False,
                                ),
                            },
                        ],
                        "temperature": 1.0,
                        "max_tokens": settings.ai_summary_max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = str(data["choices"][0]["message"]["content"]).strip()
                parsed = self._parse_json_object(content)
                label = str(parsed.get("narrative_label", "")).strip()
                summary = str(parsed.get("ai_summary", "")).strip()
                aliases = [str(item).strip() for item in parsed.get("ai_aliases", []) if str(item).strip()][:4]
                if not label or not summary:
                    return fallback
                return {
                    "narrative_label": label,
                    "ai_aliases": aliases,
                    "ai_summary": summary,
                }
        except Exception:
            return fallback

    def _parse_json_object(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", content, re.IGNORECASE)
        if fenced:
            return json.loads(fenced.group(1))

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])

        raise ValueError("no_json_object_found")

    def generate_probe_question(
        self,
        session_snapshot: dict[str, object],
        probe_candidates: list[dict[str, str]],
        runtime_config: AIProviderConfig | None,
        preferred_mode: str = "statement",
    ) -> dict[str, Any]:
        active_config = self._resolve_config(runtime_config)
        fallback = self._fallback_probe_question(probe_candidates, preferred_mode)
        if active_config is None:
            return fallback

        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.post(
                    f"{active_config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_config.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "你是 Distilled TI 的 probing 题设计器。"
                                    "只返回一个最值得追问的方向，并输出纯 JSON。"
                                    '{"probe_key":"...","probe_mode":"statement|contrast","prompt":"...","left_anchor":"...","right_anchor":"...","scenario_tags":["..."]}'
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "session_digest": session_snapshot,
                                        "probe_candidates": probe_candidates,
                                        "preferred_mode": preferred_mode,
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        ],
                        "temperature": 0.7,
                        "max_tokens": 220,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = str(data["choices"][0]["message"]["content"]).strip()
                parsed = self._parse_json_object(content)
                prompt = str(parsed.get("prompt", "")).strip()
                probe_key = str(parsed.get("probe_key", "")).strip()
                probe_mode = str(parsed.get("probe_mode", "statement")).strip() or "statement"
                if probe_mode == "contrast":
                    errors = validate_contrast_probe(
                        prompt,
                        str(parsed.get("left_anchor", "")).strip(),
                        str(parsed.get("right_anchor", "")).strip(),
                    )
                else:
                    errors = validate_likert_prompt(prompt)
                if not prompt or not probe_key or errors:
                    return fallback
                parsed["prompt"] = prompt
                parsed["probe_key"] = probe_key
                parsed["probe_mode"] = probe_mode
                parsed["scenario_tags"] = [str(tag) for tag in parsed.get("scenario_tags", [])][:3]
                return parsed
        except Exception:
            return fallback

    def generate_galgame_scene(
        self,
        scene_payload: dict[str, object],
        runtime_config: AIProviderConfig | None = None,
    ) -> dict[str, object] | None:
        active_config = self._resolve_config(runtime_config)
        if active_config is None or not settings.galgame_ai_scene_enabled:
            return None

        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.post(
                    f"{active_config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_config.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "你是一个 AI galgame 剧情引擎。像 AI-GAL 一样，根据主题、人物、最近剧情和玩家上一轮选择继续写下一幕。"
                                    "可以有校园悬疑、社团冲突、暧昧关系、轻喜剧、突发事件和分支张力；不要写成问卷，也不要解释测量目的。"
                                    "唯一硬规则：choice_texts 的 key 必须沿用输入里的 option_key；不要直接给玩家下心理诊断。"
                                    "同时为每一幕生成可给生图模型使用的英文素材提示："
                                    "background_prompt 写视觉小说背景图提示，强调场景、时间、光线、构图，必须 no humans/no text；"
                                    "character_prompt 写正面半身立绘提示，非色情、非暴露，保留角色气质。"
                                    "输出纯 JSON："
                                    '{"title":"...","location":"...","mood":"...","speaker":"...",'
                                    '"narrator_text":"...","character_text":"...",'
                                    '"choice_texts":{"option_key":"场景化选项文本"},'
                                    '"background_key":"...","background_prompt":"...",'
                                    '"character_key":"...","character_prompt":"..."}'
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(scene_payload, ensure_ascii=False),
                            },
                        ],
                        "temperature": 0.85,
                        "max_tokens": 700,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = str(data["choices"][0]["message"]["content"]).strip()
                parsed = self._parse_json_object(content)
        except Exception:
            return None

        required = ["title", "location", "mood", "speaker", "narrator_text", "character_text"]
        if any(not str(parsed.get(key, "")).strip() for key in required):
            return None
        option_keys = {
            str(choice.get("option_key"))
            for choice in scene_payload.get("choices", [])
            if isinstance(choice, dict) and choice.get("option_key")
        }
        raw_choice_texts = parsed.get("choice_texts", {})
        if not isinstance(raw_choice_texts, dict):
            raw_choice_texts = {}
        choice_texts = {
            key: str(value).strip()
            for key, value in raw_choice_texts.items()
            if key in option_keys and str(value).strip()
        }
        parsed["choice_texts"] = choice_texts
        return parsed

    def classify_galgame_free_text(
        self,
        custom_text: str | None,
        choices: list[GalgameChoice],
        runtime_config: AIProviderConfig | None = None,
    ) -> GalgameTextInference:
        text = (custom_text or "").strip()
        if not text:
            return GalgameTextInference(source="none", reason="no_custom_text")

        embedding_distribution, embedding_similarity = self._embedding_classify_galgame_text(text, choices)
        pairwise_distribution, pairwise_scores = self._pairwise_classify_galgame_text(text, choices, embedding_similarity)
        llm_distribution: dict[str, float] = {}
        llm_reason = ""
        active_config = self._resolve_config(runtime_config)
        if active_config is not None:
            try:
                with httpx.Client(timeout=12.0, follow_redirects=False) as client:
                    response = client.post(
                        f"{active_config.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {active_config.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": active_config.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "你是自由台词倾向分类器。"
                                        "只判断玩家这句台词在当前剧情里更接近哪个已给选项；不做心理诊断。"
                                        "请同时给出每个 option_key 的 0-1 倾向分布，分布总和接近 1。"
                                        "如果证据不足，分布要更平，confidence 必须低。"
                                        "输出纯 JSON："
                                        '{"option_key":"...","confidence":0.0,"reason":"...",'
                                        '"option_scores":[{"option_key":"...","score":0.0,"reason":"..."}]}'
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": json.dumps(
                                        {
                                            "custom_text": text,
                                            "choices": [
                                                {
                                                    "option_key": choice.option_key,
                                                    "text": choice.text,
                                                    "score": choice.score,
                                                }
                                                for choice in choices
                                            ],
                                        },
                                        ensure_ascii=False,
                                    ),
                                },
                            ],
                            "temperature": 0.0,
                            "max_tokens": 160,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    parsed = self._parse_json_object(str(data["choices"][0]["message"]["content"]).strip())
                    llm_distribution = self._parse_option_distribution(parsed, choices)
                    llm_reason = str(parsed.get("reason", "")).strip()[:180]
            except Exception:
                pass

        if llm_distribution or embedding_distribution or pairwise_distribution:
            return self._fuse_galgame_inference(
                choices=choices,
                llm_distribution=llm_distribution,
                embedding_distribution=embedding_distribution,
                embedding_similarity=embedding_similarity,
                pairwise_distribution=pairwise_distribution,
                pairwise_scores=pairwise_scores,
                llm_reason=llm_reason,
            )
        return self._rule_classify_galgame_text(text, choices)

    def classify_galgame_free_text_offline(
        self,
        custom_text: str | None,
        choices: list[GalgameChoice],
    ) -> GalgameTextInference:
        """Deterministic no-network classifier used by calibration tests/scripts."""
        text = (custom_text or "").strip()
        if not text:
            return GalgameTextInference(source="none", reason="no_custom_text")
        pairwise_distribution, pairwise_scores = self._pairwise_classify_galgame_text(text, choices, {})
        if pairwise_distribution:
            return self._fuse_galgame_inference(
                choices=choices,
                llm_distribution={},
                embedding_distribution={},
                embedding_similarity={},
                pairwise_distribution=pairwise_distribution,
                pairwise_scores=pairwise_scores,
                llm_reason="",
            )
        return self._rule_classify_galgame_text(text, choices)

    def _embedding_classify_galgame_text(
        self,
        text: str,
        choices: list[GalgameChoice],
    ) -> tuple[dict[str, float], dict[str, float]]:
        if not choices or not embedding_service.can_embed():
            return {}, {}
        documents = [
            (
                "task=galgame_free_text_tendency\n"
                "role=player_line\n"
                f"text={text}"
            )
        ]
        documents.extend(
            (
                "task=galgame_free_text_tendency\n"
                "role=choice_anchor\n"
                f"option_key={choice.option_key}\n"
                f"score={choice.score:.3f}\n"
                f"tone={choice.tone}\n"
                f"text={choice.text}"
            )
            for choice in choices
        )
        try:
            vectors = embedding_service.embed_texts(documents)
        except EmbeddingServiceError:
            return {}, {}
        if len(vectors) != len(choices) + 1:
            return {}, {}
        query = vectors[0]
        similarities = {
            choice.option_key: round(self._cosine_similarity(query, vectors[index + 1]), 4)
            for index, choice in enumerate(choices)
        }
        return self._softmax_distribution(similarities, temperature=8.0), similarities

    def _pairwise_classify_galgame_text(
        self,
        text: str,
        choices: list[GalgameChoice],
        embedding_similarity: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, float]]:
        if not choices:
            return {}, {}
        option_keys = [choice.option_key for choice in choices]
        wins = {key: 0.0 for key in option_keys}
        comparisons = {key: 0 for key in option_keys}
        lexical_scores = self._lexical_choice_scores(text, choices)
        for left_index, left in enumerate(choices):
            for right in choices[left_index + 1 :]:
                left_score = self._pairwise_signal(text, left, embedding_similarity, lexical_scores)
                right_score = self._pairwise_signal(text, right, embedding_similarity, lexical_scores)
                probability_left = 1 / (1 + math.exp(max(-8.0, min(8.0, (right_score - left_score) * 4.0))))
                wins[left.option_key] += probability_left
                wins[right.option_key] += 1 - probability_left
                comparisons[left.option_key] += 1
                comparisons[right.option_key] += 1
        pairwise_scores = {
            key: wins[key] / max(comparisons[key], 1)
            for key in option_keys
        }
        return self._softmax_distribution(pairwise_scores, temperature=8.0), pairwise_scores

    def _pairwise_signal(
        self,
        text: str,
        choice: GalgameChoice,
        embedding_similarity: dict[str, float],
        lexical_scores: dict[str, float],
    ) -> float:
        score = 0.0
        if choice.option_key in embedding_similarity:
            score += embedding_similarity[choice.option_key] * 0.65
        score += lexical_scores.get(choice.option_key, 0.0) * 0.25
        score += self._score_direction_prior(text, choice.score) * 0.10
        return score

    def _lexical_choice_scores(self, text: str, choices: list[GalgameChoice]) -> dict[str, float]:
        text_tokens = self._char_bigrams(text)
        scores: dict[str, float] = {}
        for choice in choices:
            choice_tokens = self._char_bigrams(choice.text)
            if not text_tokens or not choice_tokens:
                scores[choice.option_key] = 0.0
                continue
            overlap = len(text_tokens & choice_tokens)
            union = len(text_tokens | choice_tokens)
            scores[choice.option_key] = overlap / max(union, 1)
        return scores

    def _char_bigrams(self, text: str) -> set[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        if len(normalized) <= 1:
            return {normalized} if normalized else set()
        return {normalized[index : index + 2] for index in range(len(normalized) - 1)}

    def _score_direction_prior(self, text: str, score: float) -> float:
        lowered = text.lower()
        if any(marker in lowered for marker in ["观察", "暂时", "看看", "不表态", "折中", "看情况", "放慢", "observe", "wait"]):
            target = 0.0
        elif any(marker in lowered for marker in ["推进", "主动", "接受", "支持", "接下", "开口", "安排", "定下来", "行动", "offer", "push"]):
            target = 1.0
        elif any(marker in lowered for marker in ["拒绝", "后撤", "不想", "不会", "不接", "边界", "退后", "avoid", "decline"]):
            target = -1.0
        else:
            target = 0.0
        return 1 - min(abs(score - target), 2.0) / 2.0

    def _parse_option_distribution(
        self,
        parsed: dict[str, Any],
        choices: list[GalgameChoice],
    ) -> dict[str, float]:
        allowed = {choice.option_key for choice in choices}
        raw_scores: dict[str, float] = {}
        raw_option_scores = parsed.get("option_scores")
        if isinstance(raw_option_scores, list):
            for item in raw_option_scores:
                if not isinstance(item, dict):
                    continue
                option_key = str(item.get("option_key", "")).strip()
                if option_key not in allowed:
                    continue
                try:
                    raw_scores[option_key] = max(0.0, float(item.get("score", 0.0)))
                except (TypeError, ValueError):
                    continue

        if not raw_scores and isinstance(parsed.get("distribution"), dict):
            for option_key, value in parsed["distribution"].items():
                key = str(option_key).strip()
                if key not in allowed:
                    continue
                try:
                    raw_scores[key] = max(0.0, float(value))
                except (TypeError, ValueError):
                    continue

        option_key = str(parsed.get("option_key", "")).strip()
        if not raw_scores and option_key in allowed:
            try:
                confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
            except (TypeError, ValueError):
                confidence = 0.0
            remainder = max(0.0, 1.0 - confidence)
            other_keys = [choice.option_key for choice in choices if choice.option_key != option_key]
            raw_scores[option_key] = confidence
            for key in other_keys:
                raw_scores[key] = remainder / max(len(other_keys), 1)

        return self._normalize_distribution(raw_scores)

    def _fuse_galgame_inference(
        self,
        *,
        choices: list[GalgameChoice],
        llm_distribution: dict[str, float],
        embedding_distribution: dict[str, float],
        embedding_similarity: dict[str, float],
        pairwise_distribution: dict[str, float],
        pairwise_scores: dict[str, float],
        llm_reason: str,
    ) -> GalgameTextInference:
        option_keys = [choice.option_key for choice in choices]
        fused: dict[str, float] = {}
        llm_available = bool(llm_distribution)
        embedding_available = bool(embedding_distribution)
        pairwise_available = bool(pairwise_distribution)
        total_weight = (0.56 if llm_available else 0.0) + (0.24 if embedding_available else 0.0) + (0.20 if pairwise_available else 0.0)
        if total_weight <= 0:
            total_weight = 1.0
        llm_weight = (0.56 if llm_available else 0.0) / total_weight
        embedding_weight = (0.24 if embedding_available else 0.0) / total_weight
        pairwise_weight = (0.20 if pairwise_available else 0.0) / total_weight

        for key in option_keys:
            fused[key] = (
                llm_weight * llm_distribution.get(key, 0.0)
                + embedding_weight * embedding_distribution.get(key, 0.0)
                + pairwise_weight * pairwise_distribution.get(key, 0.0)
            )
        fused = self._normalize_distribution(fused)
        selected_key = max(fused, key=fused.get) if fused else None
        confidence = fused.get(selected_key, 0.0) if selected_key else 0.0
        llm_top = max(llm_distribution, key=llm_distribution.get) if llm_distribution else None
        embedding_top = max(embedding_distribution, key=embedding_distribution.get) if embedding_distribution else None
        pairwise_top = max(pairwise_distribution, key=pairwise_distribution.get) if pairwise_distribution else None
        if sum(bool(value) for value in [llm_available, embedding_available, pairwise_available]) >= 2:
            source = "hybrid"
            if len({top for top in [llm_top, embedding_top, pairwise_top] if top}) == 1:
                reason = f"LLM、embedding 或 pairwise 证据共同指向 {selected_key}。"
            else:
                reason = f"融合判断选择 {selected_key}；LLM={llm_top or 'none'}，embedding={embedding_top or 'none'}，pairwise={pairwise_top or 'none'}。"
        elif llm_available:
            source = "llm"
            reason = llm_reason or f"LLM 分类指向 {selected_key}。"
        elif embedding_available:
            source = "embedding"
            reason = f"embedding 语义近邻指向 {selected_key}。"
        else:
            source = "pairwise"
            reason = f"pairwise 比较器指向 {selected_key}。"
        if llm_reason and source == "hybrid":
            reason = f"{reason} LLM 依据：{llm_reason}"

        option_scores = [
            GalgameOptionTendency(
                option_key=choice.option_key,
                llm_score=round(llm_distribution[choice.option_key], 3) if choice.option_key in llm_distribution else None,
                embedding_score=round(embedding_distribution[choice.option_key], 3) if choice.option_key in embedding_distribution else None,
                pairwise_score=round(pairwise_distribution[choice.option_key], 3) if choice.option_key in pairwise_distribution else None,
                fused_score=round(fused.get(choice.option_key, 0.0), 3),
                reason=self._option_reason(choice, selected_key, embedding_similarity),
            )
            for choice in choices
        ]
        option_scores.sort(key=lambda item: item.fused_score, reverse=True)
        return GalgameTextInference(
            inferred_option_key=selected_key,
            confidence=round(confidence, 3),
            reason=reason[:220],
            source=source,  # type: ignore[arg-type]
            option_scores=option_scores,
            embedding_available=embedding_available,
            pairwise_available=pairwise_available,
            llm_available=llm_available,
        )

    def _option_reason(
        self,
        choice: GalgameChoice,
        selected_key: str | None,
        embedding_similarity: dict[str, float],
    ) -> str:
        marker = "selected" if choice.option_key == selected_key else "candidate"
        if choice.option_key in embedding_similarity:
            return f"{marker}; embedding_similarity={embedding_similarity[choice.option_key]:.3f}"
        return marker

    def _normalize_distribution(self, scores: dict[str, float]) -> dict[str, float]:
        total = sum(max(0.0, value) for value in scores.values())
        if total <= 0:
            return {}
        return {key: round(max(0.0, value) / total, 4) for key, value in scores.items()}

    def _softmax_distribution(self, similarities: dict[str, float], temperature: float) -> dict[str, float]:
        if not similarities:
            return {}
        maximum = max(similarities.values())
        exp_scores = {
            key: math.exp((value - maximum) * temperature)
            for key, value in similarities.items()
        }
        return self._normalize_distribution(exp_scores)

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def summarize_report_with_config(
        self,
        report_payload: dict[str, object],
        runtime_config: AIProviderConfig | None,
    ) -> str:
        active_config = self._resolve_config(runtime_config)
        if active_config is None:
            return self._fallback_summary(report_payload)

        try:
            with httpx.Client(timeout=20.0, follow_redirects=False) as client:
                response = client.post(
                    f"{active_config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": active_config.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "你是 Distilled TI 的报告总结器，输出简洁、有辨识度的中文摘要。",
                            },
                            {
                                "role": "user",
                                "content": (
                                    "请根据以下 JSON 画像数据输出 180-260 字的中文报告摘要：\n"
                                    f"{json.dumps(report_payload, ensure_ascii=False)}"
                                ),
                            },
                        ],
                        "temperature": 0.6,
                        "max_tokens": settings.ai_summary_max_tokens,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return str(data["choices"][0]["message"]["content"]).strip()
        except Exception:
            return self._fallback_summary(report_payload)

    def _rule_classify_galgame_text(self, text: str, choices: list[GalgameChoice]) -> GalgameTextInference:
        lowered = text.lower()
        neutral_markers = ["不确定", "看情况", "观察", "折中", "先看看", "暂时", "再说", "balanced", "observe"]
        positive_markers = ["同意", "推进", "主动", "支持", "愿意", "接受", "会做", "往前", "plan", "offer"]
        negative_markers = ["不同意", "拒绝", "后撤", "不想", "不会", "反对", "停止", "退后", "avoid", "wait"]
        if any(marker in lowered for marker in neutral_markers):
            target_score = 0.0
            reason = "规则回退：台词包含观望或折中信号。"
        elif any(marker in lowered for marker in negative_markers):
            target_score = -1.0
            reason = "规则回退：台词包含后撤或否定信号。"
        elif any(marker in lowered for marker in positive_markers):
            target_score = 1.0
            reason = "规则回退：台词包含主动推进或肯定信号。"
        else:
            option_scores = [
                GalgameOptionTendency(option_key=choice.option_key, fused_score=round(1 / max(len(choices), 1), 3), reason="rule_uncertain")
                for choice in choices
            ]
            return GalgameTextInference(
                confidence=0.2,
                reason="规则回退：没有足够明确的倾向词。",
                source="rule",
                option_scores=option_scores,
            )

        selected = min(choices, key=lambda choice: abs(choice.score - target_score))
        distribution = {
            choice.option_key: (0.62 if choice.option_key == selected.option_key else 0.38 / max(len(choices) - 1, 1))
            for choice in choices
        }
        return GalgameTextInference(
            inferred_option_key=selected.option_key,
            confidence=0.62,
            reason=reason,
            source="rule",
            option_scores=[
                GalgameOptionTendency(
                    option_key=choice.option_key,
                    fused_score=round(distribution[choice.option_key], 3),
                    reason="rule_selected" if choice.option_key == selected.option_key else "rule_alternative",
                )
                for choice in choices
            ],
        )

    def _fallback_summary(self, report_payload: dict[str, object]) -> str:
        structural = report_payload.get("structural_labels", [])
        if structural:
            labels = "、".join(str(item["label"]) for item in structural[:3] if "label" in item)
        else:
            labels = "核心维度"
        return (
            f"当前数据更倾向于在 {labels} 上表现出相对清晰的轮廓。"
            "系统已经开始看到你在推进方式、判断习惯和互动风格上的稳定信号，"
            "但其中一部分细节仍会随着更多题目继续被校准和细化。"
        )

    def _fallback_probe_question(self, probe_candidates: list[dict[str, str]], preferred_mode: str = "statement") -> dict[str, Any]:
        selected = probe_candidates[0]
        fallback_prompt = selected.get(
            "fallback_prompt",
            "面对一个需要你给出真实偏好的判断时，我通常不会只按最省事的标准选。",
        )
        if preferred_mode == "contrast":
            left_anchor = str(selected.get("contrast_left", "")).strip()
            right_anchor = str(selected.get("contrast_right", "")).strip()
            if left_anchor and right_anchor:
                return {
                    "probe_key": selected["key"],
                    "probe_mode": "contrast",
                    "prompt": "面对这个方向时，你的偏好更接近哪一侧？",
                    "left_anchor": left_anchor,
                    "right_anchor": right_anchor,
                    "scenario_tags": [selected.get("safe_domain", "probe"), "ai_probe", "contrast"],
                }
        return {
            "probe_key": selected["key"],
            "probe_mode": "statement",
            "prompt": fallback_prompt,
            "scenario_tags": [selected.get("safe_domain", "probe"), "ai_probe"],
        }

    def _fallback_rewrite(self, prompt: str, style_hint: str | None = None) -> str:
        return prompt

    def _fallback_candidates(
        self,
        prompt: str,
        style_hint: str | None,
        candidate_count: int,
        seed_key: str | None = None,
    ) -> list[dict[str, object]]:
        style_frames = self._style_frame_pool(style_hint)
        rng = random.Random(seed_key or f"{prompt}|{style_hint or 'default'}")
        style_frames = style_frames[:]
        rng.shuffle(style_frames)
        candidates: list[str] = [self._fallback_rewrite(prompt, style_hint)]
        candidates.extend(frame.format(prompt=prompt.rstrip("。")) for frame in style_frames)
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = re.sub(r"\s+", "", candidate)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "rewritten_prompt": candidate,
                    "generation_mode": "template",
                    "validator_passed": len(validate_generated_prompt(candidate)) == 0,
                }
            )
            if len(normalized) >= candidate_count:
                break
        return normalized

    def _style_frame_pool(self, style_hint: str | None) -> list[str]:
        playful_frames = [
            "群聊已经静了十几秒，轮到有人把局面点亮了。{prompt}。",
            "桌上的空气卡在那里，总得有人先把第一块骨头拆出来。{prompt}。",
            "截止时间突然往前撞了一截。{prompt}。",
            "体面和进度开始打架了。{prompt}。",
            "大家嘴上都说再看看，但窗口其实不会一直开着。{prompt}。",
            "场面还没坏，可那点别扭已经够明显了。{prompt}。",
            "信息没齐，节奏却在催人往前。{prompt}。",
            "这不是纸上推演，今晚就会见真章。{prompt}。",
            "讨论转了三圈，最缺的不是观点，是有人先落一步。{prompt}。",
            "一个小圈子里的人都很会说，但眼下更缺把话变成动作的人。{prompt}。",
            "房间里每个人都知道再拖会变形，只是还没人先动刀。{prompt}。",
            "你刚进场，局面还浮着，没有谁真正把重心压下去。{prompt}。",
        ]
        if not style_hint:
            return playful_frames

        profile = style_hint.lower()
        if "细微" in profile or "差别" in profile:
            return [
                "外人看都差不多，但你知道分寸一偏，结果就会改样。{prompt}。",
                "这里真正拉开差距的，不是能力总量，而是临门一脚的拿捏。{prompt}。",
                "别人已经觉得差不多了，你却知道关键还卡在那一点。{prompt}。",
                "问题不在方向对不对，而在节奏和门槛压在哪。{prompt}。",
                "局面表面上平，可真正决定结果的是那点细小偏移。{prompt}。",
            ]
        if "门槛" in profile or "细分" in profile:
            return [
                "麻烦的从来不是做不做，而是做到哪一步才算真的开始。{prompt}。",
                "局面已经逼到会暴露真实门槛的位置了。{prompt}。",
                "原则谁都会讲，眼下更缺的是先把第一步压到地上。{prompt}。",
                "事情已经走进再拖就会变样的区间。{prompt}。",
                "真正考人的不是口头态度，而是你把门槛放在哪。{prompt}。",
            ]
        return playful_frames


ai_service = AIService()
