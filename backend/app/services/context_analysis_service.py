"""Universal context support-signal analysis API.

This service intentionally emits non-diagnostic support and safety signals.
It is designed for authorized product safety workflows, not covert medical
diagnosis or automated clinical decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
import re
from typing import Any
from uuid import uuid4

import httpx

from app.core.config import settings
from app.domain.models import (
    ContextAnalysisMessage,
    ContextAnalysisRecord,
    ContextAnalysisResponse,
    ContextAnalysisSignal,
)
from app.services.ai_service import ai_service
from app.services.embedding_service import EmbeddingServiceError, embedding_service
from app.services.storage import local_session_store


RISK_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "crisis": 4}
SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3, "crisis": 4}


class ContextAnalysisService:
    """Analyze arbitrary chat context with rules, embeddings, and optional LLM."""

    _rule_specs: tuple[dict[str, object], ...] = (
        {
            "key": "direct_self_harm_or_suicide_language",
            "label": "直接自伤或自杀表达",
            "severity": "crisis",
            "risk_level": "crisis",
            "confidence": 0.96,
            "patterns": (
                r"\b(kill myself|end my life|suicide|want to die|going to die)\b",
                r"(自杀|轻生|结束生命|不想活|想死|杀了我自己|了结自己)",
            ),
            "action": "立即触发危机支持流程；提供 988/本地紧急资源，并交由受训人员人工复核。",
        },
        {
            "key": "method_plan_or_goodbye_signal",
            "label": "可能存在计划、方法或告别信号",
            "severity": "crisis",
            "risk_level": "crisis",
            "confidence": 0.9,
            "patterns": (
                r"\b(suicide plan|suicide method|kill myself.{0,40}(plan|method)|final note|goodbye forever|jump off|overdose)\b",
                r"((自杀|轻生).{0,20}(方法|计划)|遗书|最后一次告别|跳楼|吞药|割腕|再见了这个世界)",
            ),
            "action": "当上下文同时出现自伤意图时按危机处理；否则进入高优先级人工复核。",
        },
        {
            "key": "hopeless_trapped_burden_language",
            "label": "绝望、被困或成为负担的表达",
            "severity": "high",
            "risk_level": "high",
            "confidence": 0.78,
            "patterns": (
                r"\b(hopeless|trapped|no way out|no reason to live|burden|worthless)\b",
                r"(没有希望|没救了|走不出去|没有意义|我是负担|拖累|活着没意思)",
            ),
            "action": "提供支持性回应、降低任务压力，并建议人工复核最近上下文。",
        },
        {
            "key": "unbearable_pain_or_extreme_distress",
            "label": "不可承受痛苦或极端痛苦表达",
            "severity": "high",
            "risk_level": "high",
            "confidence": 0.74,
            "patterns": (
                r"\b(unbearable|can't take it|cannot take it|too much pain|breaking down)\b",
                r"(受不了了|撑不住|太痛苦|崩溃|扛不住|快疯了)",
            ),
            "action": "建议暂停普通对话流程，转为支持性安全询问或人工接管。",
        },
        {
            "key": "withdrawal_or_isolation",
            "label": "退缩、孤立或断联信号",
            "severity": "medium",
            "risk_level": "medium",
            "confidence": 0.58,
            "patterns": (
                r"\b(no one cares|alone|isolated|withdraw|disappear)\b",
                r"(没人关心|只有我一个人|孤立|消失|不想见人|断联)",
            ),
            "action": "提示助手保持陪伴式回应，并在后续轮次持续观察变化趋势。",
        },
        {
            "key": "sleep_substance_or_function_change",
            "label": "睡眠、物质使用或功能状态变化",
            "severity": "low",
            "risk_level": "low",
            "confidence": 0.48,
            "patterns": (
                r"\b(can't sleep|sleep all day|drinking more|using drugs|panic attack)\b",
                r"(睡不着|一直睡|喝酒|嗑药|药物|惊恐|吃不下|暴食)",
            ),
            "action": "建议记录为长期趋势信号，不单独作为高风险判断。",
        },
    )

    _embedding_anchors: dict[str, str] = {
        "direct_self_harm_or_suicide_language": "The user says they want to die, kill themselves, end their life, or commit suicide.",
        "method_plan_or_goodbye_signal": "The user describes a suicide method, plan, final note, goodbye, or preparing to die.",
        "hopeless_trapped_burden_language": "The user feels hopeless, trapped, worthless, or like a burden to others.",
        "unbearable_pain_or_extreme_distress": "The user describes unbearable emotional pain, panic, rage, or extreme distress.",
        "withdrawal_or_isolation": "The user is withdrawing, disappearing, isolating from friends, or says nobody cares.",
        "sleep_substance_or_function_change": "The user describes sleep disruption, substance use, appetite change, or daily functioning decline.",
    }

    def analyze(
        self,
        *,
        application_id: str,
        external_user_id: str,
        conversation_id: str,
        messages: list[ContextAnalysisMessage],
        consent_basis: str,
        channel: str = "chat",
        locale: str = "zh-CN",
        metadata: dict[str, Any] | None = None,
        persist: bool = True,
        persist_messages: bool = False,
        include_debug: bool = False,
    ) -> ContextAnalysisResponse:
        if not consent_basis.strip():
            raise ValueError("consent_basis_required")
        if not messages:
            raise ValueError("messages_required")

        now = datetime.now(UTC)
        analysis_id = str(uuid4())
        recent_messages = messages[-max(settings.context_analysis_recent_message_limit, 1) :]
        user_text = self._join_user_text(recent_messages)
        all_text = self._join_all_text(recent_messages)

        rule_signals = self._rule_signals(user_text)
        embedding_signals, embedding_debug = self._embedding_signals(user_text)
        llm_signals, llm_level, llm_confidence, llm_debug = self._llm_signals(
            all_text=all_text,
            application_id=application_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            channel=channel,
            locale=locale,
            metadata=metadata or {},
        )

        signals = self._merge_signals([*rule_signals, *embedding_signals, *llm_signals])
        risk_level, risk_score = self._risk_level(signals, llm_level, llm_confidence)
        cluster = self._cluster_for(risk_level, signals)
        confidence = self._confidence(signals, llm_confidence)
        immediate_actions = self._actions_for(risk_level, signals)
        evidence_window = self._evidence_window(recent_messages)

        response = ContextAnalysisResponse(
            analysis_id=analysis_id,
            application_id=application_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            risk_level=risk_level,
            risk_score=risk_score,
            cluster=cluster,
            confidence=confidence,
            signals=signals,
            immediate_actions=immediate_actions,
            escalation_required=risk_level == "crisis",
            human_review_recommended=RISK_ORDER[risk_level] >= RISK_ORDER["medium"],
            evidence_window=evidence_window,
            model_usage={
                "rule": {"enabled": True, "signal_count": len(rule_signals)},
                "embedding": embedding_debug if include_debug else {"enabled": embedding_debug.get("enabled", False)},
                "llm": llm_debug if include_debug else {"enabled": llm_debug.get("enabled", False)},
                "channel": channel,
                "locale": locale,
            },
            created_at=now,
        )

        if persist:
            request_payload: dict[str, object] = {
                "application_id": application_id,
                "external_user_id": external_user_id,
                "conversation_id": conversation_id,
                "channel": channel,
                "locale": locale,
                "metadata": metadata or {},
                "consent_basis": consent_basis,
                "message_count": len(messages),
                "persist_messages": persist_messages,
            }
            if persist_messages and settings.context_analysis_store_raw_messages:
                request_payload["messages"] = [message.model_dump(mode="json") for message in messages]
            else:
                request_payload["message_excerpt_window"] = evidence_window
            local_session_store.save_context_analysis_record(
                ContextAnalysisRecord(
                    analysis_id=analysis_id,
                    application_id=application_id,
                    external_user_id=external_user_id,
                    conversation_id=conversation_id,
                    risk_level=risk_level,
                    request_payload=request_payload,
                    response=response,
                    created_at=now,
                )
            )

        return response

    def _rule_signals(self, text: str) -> list[ContextAnalysisSignal]:
        signals: list[ContextAnalysisSignal] = []
        for spec in self._rule_specs:
            evidence: list[str] = []
            for pattern in spec["patterns"]:  # type: ignore[index]
                match = re.search(str(pattern), text, flags=re.IGNORECASE)
                if match:
                    evidence.append(self._excerpt(text, match.start(), match.end()))
            if evidence:
                signals.append(
                    ContextAnalysisSignal(
                        key=str(spec["key"]),
                        label=str(spec["label"]),
                        severity=spec["severity"],  # type: ignore[arg-type]
                        confidence=float(spec["confidence"]),
                        source="rule",
                        evidence=evidence[:3],
                        suggested_action=str(spec["action"]),
                    )
                )
        return signals

    def _embedding_signals(self, text: str) -> tuple[list[ContextAnalysisSignal], dict[str, object]]:
        if not text.strip() or not embedding_service.can_embed():
            return [], {"enabled": False, "reason": "embedding_not_configured"}
        try:
            documents = [text, *self._embedding_anchors.values()]
            vectors = embedding_service.embed_texts(documents)
        except EmbeddingServiceError as exc:
            return [], {"enabled": True, "error": str(exc)}

        query = vectors[0]
        signals: list[ContextAnalysisSignal] = []
        similarities: dict[str, float] = {}
        for key, vector in zip(self._embedding_anchors.keys(), vectors[1:], strict=True):
            similarity = self._cosine(query, vector)
            similarities[key] = round(similarity, 4)
            if similarity < 0.72:
                continue
            spec = self._spec_for(key)
            if spec is None:
                continue
            signals.append(
                ContextAnalysisSignal(
                    key=key,
                    label=str(spec["label"]),
                    severity=spec["severity"],  # type: ignore[arg-type]
                    confidence=round(min(0.9, 0.45 + similarity * 0.45), 3),
                    source="embedding",
                    evidence=[f"semantic_similarity={similarity:.3f}"],
                    suggested_action=str(spec["action"]),
                )
            )
        return signals, {"enabled": True, "similarities": similarities}

    def _llm_signals(
        self,
        *,
        all_text: str,
        application_id: str,
        external_user_id: str,
        conversation_id: str,
        channel: str,
        locale: str,
        metadata: dict[str, Any],
    ) -> tuple[list[ContextAnalysisSignal], str | None, float | None, dict[str, object]]:
        active_config = ai_service.get_config()
        if active_config is None:
            return [], None, None, {"enabled": False, "reason": "ai_provider_not_configured"}
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
                                    "你是产品安全上下文分析器，只输出非诊断的支持/风险信号。"
                                    "不要做心理疾病诊断，不要给医学结论。"
                                    "如果存在即时自伤/自杀风险，risk_level 使用 crisis。"
                                    "输出纯 JSON："
                                    '{"risk_level":"none|low|medium|high|crisis","confidence":0.0,'
                                    '"signals":[{"key":"...","label":"...","severity":"low|medium|high|crisis",'
                                    '"confidence":0.0,"evidence":["短证据"],"suggested_action":"..."}],'
                                    '"immediate_actions":["..."]}'
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "application_id": application_id,
                                        "external_user_id": external_user_id,
                                        "conversation_id": conversation_id,
                                        "channel": channel,
                                        "locale": locale,
                                        "metadata": metadata,
                                        "recent_context": all_text[-8000:],
                                    },
                                    ensure_ascii=False,
                                ),
                            },
                        ],
                        "temperature": 0,
                        "max_tokens": 800,
                    },
                )
                response.raise_for_status()
                content = str(response.json()["choices"][0]["message"]["content"]).strip()
                parsed = self._parse_json_object(content)
        except Exception as exc:
            return [], None, None, {"enabled": True, "error": str(exc)}

        risk_level = str(parsed.get("risk_level", "")).lower()
        if risk_level not in RISK_ORDER:
            risk_level = None  # type: ignore[assignment]
        confidence = self._clamp_float(parsed.get("confidence"), default=0.0)
        signals: list[ContextAnalysisSignal] = []
        for item in parsed.get("signals", []) if isinstance(parsed.get("signals"), list) else []:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "low")).lower()
            if severity not in SEVERITY_ORDER:
                severity = "low"
            signals.append(
                ContextAnalysisSignal(
                    key=self._safe_key(str(item.get("key", "llm_context_signal"))),
                    label=str(item.get("label", "LLM 上下文支持信号"))[:80],
                    severity=severity,  # type: ignore[arg-type]
                    confidence=self._clamp_float(item.get("confidence"), default=confidence or 0.5),
                    source="llm",
                    evidence=[str(value)[:180] for value in item.get("evidence", [])[:3]]
                    if isinstance(item.get("evidence"), list)
                    else [],
                    suggested_action=str(item.get("suggested_action", "建议人工复核该上下文。"))[:180],
                )
            )
        return signals, risk_level, confidence, {"enabled": True, "model": active_config.model}

    def _merge_signals(self, signals: list[ContextAnalysisSignal]) -> list[ContextAnalysisSignal]:
        by_key: dict[str, ContextAnalysisSignal] = {}
        for signal in signals:
            existing = by_key.get(signal.key)
            if existing is None:
                by_key[signal.key] = signal
                continue
            severity = (
                signal.severity
                if SEVERITY_ORDER[signal.severity] > SEVERITY_ORDER[existing.severity]
                else existing.severity
            )
            source = existing.source if existing.source == signal.source else "hybrid"
            evidence = [*existing.evidence]
            for item in signal.evidence:
                if item not in evidence:
                    evidence.append(item)
            by_key[signal.key] = existing.model_copy(
                update={
                    "severity": severity,
                    "confidence": round(max(existing.confidence, signal.confidence), 3),
                    "source": source,
                    "evidence": evidence[:5],
                }
            )
        return sorted(
            by_key.values(),
            key=lambda item: (SEVERITY_ORDER[item.severity], item.confidence),
            reverse=True,
        )

    def _risk_level(
        self,
        signals: list[ContextAnalysisSignal],
        llm_level: str | None,
        llm_confidence: float | None,
    ) -> tuple[str, float]:
        score = 0.0
        level = "none"
        for signal in signals:
            contribution = {
                "low": 0.18,
                "medium": 0.42,
                "high": 0.68,
                "crisis": 0.95,
            }[signal.severity] * max(signal.confidence, 0.2)
            score = max(score, contribution)
            if SEVERITY_ORDER[signal.severity] >= RISK_ORDER.get(level, 0):
                level = "high" if signal.severity == "high" else signal.severity
        if llm_level in RISK_ORDER and llm_confidence:
            llm_score = min(1.0, RISK_ORDER[llm_level] / 4 + llm_confidence * 0.22)
            score = max(score, llm_score)
            if RISK_ORDER[llm_level] > RISK_ORDER[level]:
                level = llm_level
        if score < 0.12 and not signals:
            return "none", 0.0
        if level == "none":
            if score >= 0.78:
                level = "high"
            elif score >= 0.45:
                level = "medium"
            else:
                level = "low"
        return level, round(min(score, 1.0), 3)

    def _cluster_for(self, risk_level: str, signals: list[ContextAnalysisSignal]) -> str:
        keys = {signal.key for signal in signals}
        if risk_level == "crisis":
            return "acute_safety_escalation"
        if {"hopeless_trapped_burden_language", "unbearable_pain_or_extreme_distress"} & keys:
            return "distress_escalation_watch"
        if {"withdrawal_or_isolation", "sleep_substance_or_function_change"} & keys:
            return "longitudinal_support_watch"
        if risk_level in {"low", "medium"}:
            return "general_support_signal"
        return "no_current_support_signal"

    def _actions_for(self, risk_level: str, signals: list[ContextAnalysisSignal]) -> list[str]:
        if risk_level == "crisis":
            return [
                "如果用户在美国且存在即时危险，提示其拨打或短信 988；如有迫在眉睫的安全风险，联系当地紧急服务。",
                "停止普通产品推荐或闲聊优化，进入受训人员人工复核/安全支持流程。",
                "避免争辩、羞辱或承诺保密；使用支持性语言并询问其是否处于立即危险中。",
            ]
        if risk_level == "high":
            return [
                "建议人工复核最近上下文，并提供危机/心理支持资源入口。",
                "降低模型回复的任务压力，优先采用陪伴、澄清和安全计划式回应。",
            ]
        if risk_level == "medium":
            return ["建议持续观察后续上下文，并在产品内提供暂停、求助或人工支持入口。"]
        if risk_level == "low":
            return ["记录为长期趋势信号，不单独触发危机流程。"]
        return []

    def _confidence(self, signals: list[ContextAnalysisSignal], llm_confidence: float | None) -> float:
        if not signals and not llm_confidence:
            return 0.0
        values = [signal.confidence for signal in signals]
        if llm_confidence is not None:
            values.append(llm_confidence)
        return round(max(values), 3)

    def _join_user_text(self, messages: list[ContextAnalysisMessage]) -> str:
        return "\n".join(message.content for message in messages if message.role == "user")

    def _join_all_text(self, messages: list[ContextAnalysisMessage]) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in messages)

    def _evidence_window(self, messages: list[ContextAnalysisMessage]) -> list[str]:
        excerpts: list[str] = []
        for message in messages[-8:]:
            if message.role not in {"user", "assistant"}:
                continue
            content = re.sub(r"\s+", " ", message.content).strip()
            if not content:
                continue
            excerpts.append(f"{message.role}: {content[:180]}")
        return excerpts

    def _excerpt(self, text: str, start: int, end: int) -> str:
        prefix = max(0, start - 54)
        suffix = min(len(text), end + 54)
        return re.sub(r"\s+", " ", text[prefix:suffix]).strip()[:180]

    def _spec_for(self, key: str) -> dict[str, object] | None:
        return next((spec for spec in self._rule_specs if spec["key"] == key), None)

    def _cosine(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _clamp_float(self, value: object, default: float) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 3)
        except (TypeError, ValueError):
            return default

    def _parse_json_object(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("llm_json_not_object")
        return parsed

    def _safe_key(self, value: str) -> str:
        key = re.sub(r"[^a-zA-Z0-9_:-]+", "_", value.strip().lower()).strip("_")
        return key[:64] or "llm_context_signal"


context_analysis_service = ContextAnalysisService()
