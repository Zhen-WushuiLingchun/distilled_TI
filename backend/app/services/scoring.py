"""Scoring engine for the backend MVP."""

from __future__ import annotations

from math import sqrt, tanh

from app.core.config import settings
from app.domain.dimensions import (
    CORE_DIMENSION_LABELS,
    MODULE_LABELS,
    SUBDIMENSION_LABELS,
    SUBDIMENSION_TO_PARENT,
)
from app.domain.models import (
    AnswerRecord,
    AssessmentSignal,
    AssessmentSignalSourceMode,
    ItemTemplate,
    SessionReport,
    SessionState,
    StructuralLabel,
    SupportRiskFlag,
)
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.clustering import clustering_service
from app.services.reporting import build_module_insights, build_subdimension_insights, render_narrative_label


def clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


class ScoringEngine:
    def predict_score(self, state: SessionState, item: ItemTemplate) -> float:
        dot_product = sum(state.core_mu.get(key, 0.0) * weight for key, weight in item.dimension_weights.items())
        return tanh(item.discrimination * (dot_product - item.difficulty))

    def predict_signal_score(self, state: SessionState, signal: AssessmentSignal) -> float:
        dot_product = sum(state.core_mu.get(key, 0.0) * weight for key, weight in signal.dimension_weights.items())
        return tanh(signal.discrimination * (dot_product - signal.difficulty))

    def build_signal_from_item_response(
        self,
        *,
        session_id: str,
        state: SessionState,
        item: ItemTemplate,
        selected_option_key: str,
        latency_ms: int | None = None,
        source_mode: AssessmentSignalSourceMode = "standard_question",
        confidence: float = 1.0,
        evidence: dict[str, object] | None = None,
    ) -> AssessmentSignal:
        option_map = {option.key: option for option in item.options}
        selected_option = option_map[selected_option_key]
        predicted_score = self.predict_score(state, item)
        observed_score = selected_option.score
        return AssessmentSignal(
            session_id=session_id,
            source_mode=source_mode,
            source_id=item.id,
            item_id=item.id,
            template_id=getattr(item, "template_id", item.id),
            selected_option_key=selected_option_key,
            observed_score=observed_score,
            predicted_score=predicted_score,
            residual=observed_score - predicted_score,
            dimension_weights=item.dimension_weights,
            subdimension_weights=item.subdimension_weights,
            module_affinities=item.module_affinities,
            discrimination=item.discrimination,
            difficulty=item.difficulty,
            confidence=clip(confidence, 0.0, 1.0),
            evidence=evidence or {},
            latency_ms=latency_ms,
        )

    def apply_signal(self, state: SessionState, signal: AssessmentSignal) -> SessionState:
        observed_score = signal.observed_score
        predicted_score = signal.predicted_score
        if predicted_score is None:
            predicted_score = self.predict_signal_score(state, signal)
        residual = signal.residual
        if residual is None:
            residual = observed_score - predicted_score

        next_state = state.model_copy(deep=True)
        eta = settings.eta0 / sqrt(1 + max(state.question_count, 0) / settings.eta_decay)

        for dimension, weight in signal.dimension_weights.items():
            current_mu = next_state.core_mu[dimension]
            updated_mu = current_mu + eta * residual * weight
            next_state.core_mu[dimension] = clip(updated_mu, -settings.score_clip, settings.score_clip)
            next_state.dimension_counts[dimension] = next_state.dimension_counts.get(dimension, 0) + 1

            current_sigma = next_state.core_sigma[dimension]
            shrink = settings.sigma_shrink * abs(weight)
            updated_sigma = current_sigma * (1 - shrink) + settings.sigma_drift
            next_state.core_sigma[dimension] = max(settings.min_sigma, updated_sigma)

        for subdimension, weight in signal.subdimension_weights.items():
            parent_dimension = SUBDIMENSION_TO_PARENT[subdimension]
            parent_count = next_state.dimension_counts.get(parent_dimension, 0)
            if parent_count >= settings.subdimension_unlock_threshold:
                if subdimension not in next_state.unlocked_subdimensions:
                    next_state.unlocked_subdimensions.append(subdimension)
                next_state.sub_counts[subdimension] = next_state.sub_counts.get(subdimension, 0) + 1
                current_sub_mu = next_state.sub_mu[subdimension]
                next_state.sub_mu[subdimension] = clip(current_sub_mu + eta * residual * weight, -settings.score_clip, settings.score_clip)
                current_sub_sigma = next_state.sub_sigma[subdimension]
                next_state.sub_sigma[subdimension] = max(settings.min_sigma, current_sub_sigma * (1 - 0.06 * abs(weight)) + settings.sigma_drift)

        for module_key, affinity in signal.module_affinities.items():
            next_state.module_counts[module_key] = next_state.module_counts.get(module_key, 0) + 1
            updated_module_score = next_state.module_scores.get(module_key, 0.0) + residual * affinity * 0.15
            next_state.module_scores[module_key] = clip(updated_module_score, -settings.score_clip, settings.score_clip)
            if abs(next_state.module_scores[module_key]) >= 0.35 and module_key not in next_state.active_modules:
                next_state.active_modules.append(module_key)

        next_state.question_count += 1
        next_state.recent_item_ids = (next_state.recent_item_ids + [signal.template_id])[-8:]
        next_state.answers.append(
            AnswerRecord(
                item_id=signal.item_id,
                template_id=signal.template_id,
                option_key=signal.selected_option_key,
                mapped_score=observed_score,
                predicted_score=predicted_score,
                residual=residual,
                latency_ms=signal.latency_ms,
            )
        )

        next_state.zeta["exploration"] = clip(0.4 + next_state.question_count * 0.04, 0.0, 1.0)
        if abs(residual) > 1.1:
            next_state.zeta["consistency"] = clip(next_state.zeta["consistency"] - 0.05, 0.0, 1.0)
        else:
            next_state.zeta["consistency"] = clip(next_state.zeta["consistency"] + 0.02, 0.0, 1.0)
        if signal.latency_ms is not None and signal.latency_ms < 1500:
            next_state.zeta["fatigue"] = clip(next_state.zeta["fatigue"] + 0.05, 0.0, 1.0)

        return next_state

    def apply_response(
        self,
        state: SessionState,
        item: ItemTemplate,
        selected_option_key: str,
        latency_ms: int | None = None,
        *,
        session_id: str = "",
        source_mode: AssessmentSignalSourceMode = "standard_question",
        confidence: float = 1.0,
        evidence: dict[str, object] | None = None,
    ) -> SessionState:
        signal = self.build_signal_from_item_response(
            session_id=session_id,
            state=state,
            item=item,
            selected_option_key=selected_option_key,
            latency_ms=latency_ms,
            source_mode=source_mode,
            confidence=confidence,
            evidence=evidence,
        )
        return self.apply_signal(state, signal)

    def build_support_risk_flags(self, state: SessionState) -> list[SupportRiskFlag]:
        flags: list[SupportRiskFlag] = []
        if state.question_count < 5:
            return flags

        recent_answers = state.answers[-8:]
        if recent_answers:
            fast_ratio = sum(1 for answer in recent_answers if answer.latency_ms is not None and answer.latency_ms < 900) / len(recent_answers)
            large_residual_ratio = sum(1 for answer in recent_answers if abs(answer.residual) > 1.2) / len(recent_answers)
            extreme_ratio = sum(1 for answer in recent_answers if abs(answer.mapped_score) >= 1.0) / len(recent_answers)
        else:
            fast_ratio = 0.0
            large_residual_ratio = 0.0
            extreme_ratio = 0.0

        if state.zeta.get("fatigue", 0.0) >= 0.45 or fast_ratio >= 0.65:
            flags.append(
                SupportRiskFlag(
                    key="interaction_fatigue_or_rushing",
                    severity="medium" if state.zeta.get("fatigue", 0.0) >= 0.6 else "low",
                    label="可能存在疲劳或快速作答信号",
                    evidence=[
                        f"fatigue={state.zeta.get('fatigue', 0.0):.2f}",
                        f"recent_fast_ratio={fast_ratio:.2f}",
                    ],
                    suggested_action="建议在界面中提供暂停、稍后继续和非评判性说明。",
                )
            )
        if state.zeta.get("consistency", 0.5) <= 0.25 or large_residual_ratio >= 0.55:
            flags.append(
                SupportRiskFlag(
                    key="low_response_consistency",
                    severity="medium",
                    label="近期回答一致性较低",
                    evidence=[
                        f"consistency={state.zeta.get('consistency', 0.5):.2f}",
                        f"recent_large_residual_ratio={large_residual_ratio:.2f}",
                    ],
                    suggested_action="建议仅作为人工复核或后续追问信号，不应直接解释为心理问题。",
                )
            )
        if extreme_ratio >= 0.8 and len(recent_answers) >= 5:
            flags.append(
                SupportRiskFlag(
                    key="high_extreme_choice_ratio",
                    severity="low",
                    label="近期极端选项比例较高",
                    evidence=[f"recent_extreme_ratio={extreme_ratio:.2f}"],
                    suggested_action="建议后续增加情境化追问，确认这是稳定偏好还是情绪化/随意选择。",
                )
            )
        return flags

    def build_report(
        self,
        session_id: str,
        state: SessionState,
        runtime_ai_config: AIProviderConfig | None = None,
        naming_style: str | None = None,
    ) -> SessionReport:
        top_dimensions = sorted(state.core_mu.items(), key=lambda item: abs(item[1]), reverse=True)[:3]
        structural_labels = [
            StructuralLabel(
                dimension=dimension,
                label=CORE_DIMENSION_LABELS.get(dimension, dimension),
                score=score,
            )
            for dimension, score in top_dimensions
        ]
        cluster_mix = clustering_service.cluster_memberships_for_state(state)
        cluster_name = cluster_mix[0].cluster_name
        cluster_label = cluster_mix[0].narrative_label
        cluster_confidence = cluster_mix[0].weight
        narrative_label = render_narrative_label(state, cluster_label)

        uncertainty_summary = {
            "avg_sigma": sum(state.core_sigma.values()) / len(state.core_sigma),
            "stable_dimensions": sum(1 for sigma in state.core_sigma.values() if sigma <= 1.0),
        }

        core_bars = {CORE_DIMENSION_LABELS[key]: self._to_percent(score) for key, score in state.core_mu.items()}
        sub_bars = {
            SUBDIMENSION_LABELS[key]: self._to_percent(state.sub_mu[key])
            for key in state.unlocked_subdimensions
            if key in state.sub_mu
        }
        module_bars = {
            MODULE_LABELS[key]: self._to_percent(score)
            for key, score in state.module_scores.items()
            if key in state.active_modules
        }
        sub_insights = build_subdimension_insights(state, self._to_percent)
        module_insights = build_module_insights(state, self._to_percent)
        salient_subdimensions = [insight.label for insight in sub_insights[:4]]
        active_module_labels = [insight.label for insight in module_insights]

        report_payload = {
            "question_count": state.question_count,
            "cluster_name": cluster_name,
            "narrative_label": narrative_label,
            "cluster_confidence": cluster_confidence,
            "cluster_mix": [membership.model_dump() for membership in cluster_mix],
            "structural_labels": [label.model_dump() for label in structural_labels],
            "core_bars": core_bars,
            "sub_bars": sub_bars,
            "module_bars": module_bars,
            "salient_subdimensions": salient_subdimensions,
            "active_module_labels": active_module_labels,
            "sub_insights": [insight.model_dump() for insight in sub_insights],
            "module_insights": [insight.model_dump() for insight in module_insights],
            "uncertainty_summary": uncertainty_summary,
            "support_risk_flags": [flag.model_dump() for flag in self.build_support_risk_flags(state)],
        }
        ai_interpretation = ai_service.interpret_report_with_config(report_payload, runtime_ai_config, naming_style)
        ai_summary = str(ai_interpretation["ai_summary"])
        narrative_label = str(ai_interpretation["narrative_label"])
        ai_aliases = [str(item) for item in ai_interpretation.get("ai_aliases", [])]

        return SessionReport(
            session_id=session_id,
            question_count=state.question_count,
            can_exit_with_report=state.question_count >= settings.min_questions_for_report,
            structural_labels=structural_labels,
            narrative_label=narrative_label,
            ai_aliases=ai_aliases,
            ai_summary=ai_summary,
            uncertainty_summary=uncertainty_summary,
            module_bars=module_bars,
            core_bars=core_bars,
            sub_bars=sub_bars,
            cluster_name=cluster_name,
            cluster_confidence=cluster_confidence,
            cluster_mix=cluster_mix,
            salient_subdimensions=salient_subdimensions,
            active_module_labels=active_module_labels,
            sub_insights=sub_insights,
            module_insights=module_insights,
            support_risk_flags=self.build_support_risk_flags(state),
            current_state=state,
        )

    def _to_percent(self, score: float) -> float:
        return round(((clip(score, -settings.score_clip, settings.score_clip) + settings.score_clip) / (2 * settings.score_clip)) * 100, 1)
