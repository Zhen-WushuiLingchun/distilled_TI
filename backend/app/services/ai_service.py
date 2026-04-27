"""Configurable AI provider helpers with persistent local config."""

from __future__ import annotations

import json
import random
import re
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings
from app.domain.models import ItemTemplate
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
                        "messages": [{"role": "user", "content": "只回复ok"}],
                        "temperature": 0,
                        "max_tokens": 10,
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
