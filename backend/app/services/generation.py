"""Template retrieval, rewrite and item instance generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import random
import re
from uuid import uuid4

from app.core.config import settings
from app.domain.models import (
    EmbeddingScoreBreakdown,
    ItemInstance,
    ItemTemplate,
    RewriteCandidate,
    RewritePreviewBundle,
    SessionRecord,
    TemplateRewritePreview,
)
from app.services.ai_service import AIProviderConfig, ai_service
from app.services.storage import local_session_store
from app.services.validators import validate_generated_prompt
from app.services.vector_indexer import vector_indexer


class GenerationService:
    def choose_template(self, session: SessionRecord, templates: list[ItemTemplate]) -> ItemTemplate:
        rng = random.Random(f"{session.session_id}:{session.state.question_count}")
        if session.state.question_count and session.state.question_count % 7 == 0:
            anchor_candidates = [template for template in templates if template.is_anchor]
            if anchor_candidates:
                recent_template_ids = self._recent_template_ids(session)
                fresh_anchors = [candidate for candidate in anchor_candidates if candidate.id not in recent_template_ids]
                pool = fresh_anchors or anchor_candidates
                return rng.choice(pool[: min(len(pool), 4)])

        recent_ids = self._recent_template_ids(session)
        fresh_candidates = [candidate for candidate in templates if candidate.id not in recent_ids]
        pool = fresh_candidates or templates
        top_window = pool[: min(len(pool), 8)]
        return rng.choice(top_window)

    def materialize_instance(
        self,
        session: SessionRecord,
        template: ItemTemplate,
        style_hint: str | None = None,
        runtime_ai_config: AIProviderConfig | None = None,
    ) -> tuple[ItemInstance, RewritePreviewBundle]:
        active_runtime_ai = runtime_ai_config or ai_service.get_config()
        active_runtime_ai = active_runtime_ai if self._should_try_ai_rewrite(session, template, active_runtime_ai) else None
        preview_bundle = self.preview_rewrite(
            session,
            template,
            style_hint,
            active_runtime_ai,
            allow_stored_config=False,
        )
        preview = preview_bundle.selected
        generation_mode = preview.generation_mode
        if template.is_anchor:
            generation_mode = "anchor"

        instance = ItemInstance(
            id=f"inst-{uuid4()}",
            template_id=template.id,
            session_id=session.session_id,
            prompt=preview.rewritten_prompt,
            question_type=template.question_type,
            layer=template.layer,
            dimension_weights=template.dimension_weights,
            subdimension_weights=template.subdimension_weights,
            module_affinities=template.module_affinities,
            discrimination=max(template.discrimination, 1.15 if template.layer == "core" else 1.0),
            difficulty=template.difficulty,
            scenario_tags=template.scenario_tags,
            is_anchor=template.is_anchor,
            allow_rewrite=template.allow_rewrite,
            options=template.options,
            generation_mode=generation_mode,
            validator_passed=preview.validator_passed,
            quality_score=preview.score,
            similarity_penalty=self._extract_similarity_penalty(preview.reasons),
            created_at=datetime.now(UTC),
        )
        return instance, preview_bundle

    def preview_rewrite(
        self,
        session: SessionRecord,
        template: ItemTemplate,
        style_hint: str | None = None,
        runtime_ai_config: AIProviderConfig | None = None,
        allow_stored_config: bool = True,
    ) -> RewritePreviewBundle:
        active_runtime_ai = runtime_ai_config or (ai_service.get_config() if allow_stored_config else None)
        retrieval_context = vector_indexer.build_rewrite_retrieval_context(template)
        if active_runtime_ai is None:
            raw_candidates = [
                {
                    "rewritten_prompt": template.prompt,
                    "generation_mode": "template",
                    "validator_passed": True,
                }
            ]
        else:
            raw_candidates = ai_service.rewrite_template_candidates(
                session.session_id,
                template,
                style_hint,
                settings.rewrite_candidate_count,
                runtime_ai_config=active_runtime_ai,
                retrieval_context=retrieval_context.model_dump() if retrieval_context else None,
            )
        deduped = self._dedupe_candidates(template.id, raw_candidates)
        ranked = sorted(
            (
                self._score_candidate(
                    template,
                    candidate["rewritten_prompt"],
                    str(candidate.get("generation_mode", "template")),
                    bool(candidate.get("validator_passed", True)),
                )
                for candidate in deduped
            ),
            key=lambda candidate: candidate.score,
            reverse=True,
        )
        if not ranked:
            fallback = self._score_candidate(template, template.prompt, "template", True)
            ranked = [fallback]
        selected_candidate = ranked[0]
        selected = TemplateRewritePreview(
            template_id=selected_candidate.template_id,
            rewritten_prompt=selected_candidate.rewritten_prompt,
            generation_mode=selected_candidate.generation_mode,
            validator_passed=selected_candidate.validator_passed,
            score=selected_candidate.score,
            reasons=selected_candidate.reasons,
            embedding_score_breakdown=selected_candidate.embedding_score_breakdown,
        )
        for index, candidate in enumerate(ranked):
            candidate_status = "validator_failed" if not candidate.validator_passed else "selected" if index == 0 else "rejected"
            vector_indexer.index_rewrite_candidate(template, candidate, candidate_status)
        return RewritePreviewBundle(
            template_id=template.id,
            selected=selected,
            candidates=ranked,
            retrieval_context=retrieval_context if retrieval_context and retrieval_context.enabled else None,
        )

    def _should_try_ai_rewrite(
        self,
        session: SessionRecord,
        template: ItemTemplate,
        runtime_ai_config: AIProviderConfig | None,
    ) -> bool:
        if runtime_ai_config is None:
            return False
        if template.is_anchor or template.layer == "probe":
            return False
        if template.allow_rewrite:
            return True
        return session.state.question_count >= settings.ai_rewrite_expand_after_question

    def recommended_style_hint(self, session: SessionRecord) -> str:
        if session.state.question_count < settings.min_questions_for_report:
            return "高辨识度、场景更具体、语气稍微更有压强"
        if session.state.question_count < 60:
            return "细分情境、更强调具体选择门槛"
        return "聚焦细微差别、避免重复、保持高区分度"

    def _dedupe_candidates(self, template_id: str, raw_candidates: list[dict[str, object]]) -> list[dict[str, object]]:
        deduped: list[dict[str, object]] = []
        seen: set[str] = set()
        accepted_prompts: list[str] = []
        for candidate in raw_candidates:
            prompt = str(candidate.get("rewritten_prompt", "")).strip()
            if not prompt:
                continue
            normalized_key = re.sub(r"[\W_]+", "", prompt.lower())
            if normalized_key in seen:
                continue
            if any(self._semantic_similarity(prompt, existing) >= 0.72 for existing in accepted_prompts):
                continue
            seen.add(normalized_key)
            accepted_prompts.append(prompt)
            deduped.append(
                {
                    "template_id": template_id,
                    "rewritten_prompt": prompt,
                    "generation_mode": candidate.get("generation_mode", "template"),
                    "validator_passed": candidate.get("validator_passed", True),
                }
            )
        return deduped

    def _score_candidate(
        self,
        template: ItemTemplate,
        prompt: str,
        generation_mode: str,
        validator_passed: bool,
    ) -> RewriteCandidate:
        reasons: list[str] = []
        score = 0.0
        if validator_passed and not validate_generated_prompt(prompt):
            score += 3.0
            reasons.append("通过约束校验")
        else:
            reasons.append("存在约束风险")

        lexical_delta = self._lexical_delta(template.prompt, prompt)
        score += lexical_delta
        reasons.append(f"相对模板有 {lexical_delta:.2f} 的措辞新颖度")

        length_score = max(0.0, 1.5 - abs(len(prompt) - settings.rewrite_target_length) / 24)
        score += length_score
        reasons.append("长度接近目标区间")

        scenario_bonus = 0.4 if any(tag in prompt for tag in ["场景", "项目", "团队", "反馈", "代价"]) else 0.0
        score += scenario_bonus
        if scenario_bonus:
            reasons.append("场景锚点更明确")

        history_similarity = self._max_historical_similarity(prompt)
        similarity_penalty = round(history_similarity * 1.4, 3)
        score -= similarity_penalty
        reasons.append(f"历史相似度惩罚 {similarity_penalty:.2f}")

        embedding_breakdown = self._embedding_breakdown(template, prompt, generation_mode)
        if embedding_breakdown is not None:
            score += embedding_breakdown.total
            reasons.append(f"向量源距离 {embedding_breakdown.source_distance_score:.2f}")
            reasons.append(f"向量重复惩罚 {embedding_breakdown.duplicate_penalty:.2f}")
            reasons.append(f"向量对齐奖励 {embedding_breakdown.alignment_bonus:.2f}")

        if generation_mode == "llm_rewrite":
            score += 0.35
            reasons.append("来自模型改写")

        return RewriteCandidate(
            template_id=template.id,
            rewritten_prompt=prompt,
            generation_mode=generation_mode,  # type: ignore[arg-type]
            validator_passed=validator_passed,
            score=round(score, 3),
            reasons=reasons,
            embedding_score_breakdown=embedding_breakdown,
        )

    def _embedding_breakdown(
        self,
        template: ItemTemplate,
        prompt: str,
        generation_mode: str,
    ) -> EmbeddingScoreBreakdown | None:
        return vector_indexer.score_rewrite_candidate(template, prompt, generation_mode)

    def _lexical_delta(self, source: str, target: str) -> float:
        source_terms = {term for term in re.split(r"[，。、“”\s]+", source) if term}
        target_terms = {term for term in re.split(r"[，。、“”\s]+", target) if term}
        if not source_terms or not target_terms:
            return 0.0
        overlap_ratio = len(source_terms & target_terms) / max(len(source_terms | target_terms), 1)
        return max(0.0, 1.2 - overlap_ratio)

    def _semantic_similarity(self, left: str, right: str) -> float:
        left_grams = self._char_ngrams(left, 3)
        right_grams = self._char_ngrams(right, 3)
        if not left_grams or not right_grams:
            return 0.0
        return len(left_grams & right_grams) / max(len(left_grams | right_grams), 1)

    def _char_ngrams(self, text: str, n: int) -> set[str]:
        normalized = re.sub(r"\s+", "", text)
        if len(normalized) < n:
            return {normalized} if normalized else set()
        return {normalized[index : index + n] for index in range(len(normalized) - n + 1)}

    def _max_historical_similarity(self, prompt: str) -> float:
        instances = local_session_store.list_item_instances()[:80]
        if not instances:
            return 0.0
        return max(self._semantic_similarity(prompt, instance.prompt) for instance in instances)

    def _extract_similarity_penalty(self, reasons: list[str]) -> float:
        for reason in reasons:
            if reason.startswith("历史相似度惩罚"):
                try:
                    return float(reason.split(" ")[-1])
                except ValueError:
                    return 0.0
        return 0.0

    def _recent_template_ids(self, session: SessionRecord) -> set[str]:
        template_ids = set(session.state.recent_item_ids)
        template_ids.update(answer.template_id for answer in session.state.answers[-settings.exact_repeat_cooldown :])
        if session.current_template_id:
            template_ids.add(session.current_template_id)
        return template_ids

    def recent_session_prompts(
        self,
        session: SessionRecord,
        resolve_prompt: Callable[[str], str | None],
        window: int | None = None,
    ) -> list[str]:
        prompts: list[str] = []
        effective_window = window or settings.semantic_repeat_window
        for answer in session.state.answers[-effective_window:]:
            prompt = resolve_prompt(answer.item_id)
            if prompt:
                prompts.append(prompt)
        return prompts

    def max_prompt_similarity(self, prompt: str, recent_prompts: list[str]) -> float:
        if not recent_prompts:
            return 0.0
        return max(self._semantic_similarity(prompt, existing) for existing in recent_prompts)


generation_service = GenerationService()
