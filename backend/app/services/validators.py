"""Validation helpers for template creation and rewriting."""

from __future__ import annotations

from app.domain.models import ItemTemplateCreate


MORALIZING_PHRASES = (
    "更成熟的人会",
    "真正优秀的人通常",
    "更聪明的人更倾向于",
)

SENSITIVE_TERMS = (
    "政治",
    "宗教",
    "创伤",
    "精神诊断",
    "医疗",
    "性隐私",
    "犯罪",
)

LIKERT_INCOMPATIBLE_PATTERNS = (
    "？",
    "?",
    "还是更",
    "更偏爱",
    "更喜欢A",
    "更喜欢B",
)


def validate_item_template(payload: ItemTemplateCreate) -> list[str]:
    errors: list[str] = []

    non_zero_dimensions = [key for key, weight in payload.dimension_weights.items() if abs(weight) > 0]
    if len(non_zero_dimensions) == 0:
        errors.append("至少需要一个核心维度载荷。")
    if len(non_zero_dimensions) > 3:
        errors.append("一题最多映射 3 个维度。")

    primary_dimensions = [key for key, weight in payload.dimension_weights.items() if abs(weight) >= 0.4]
    if len(primary_dimensions) > 2:
        errors.append("主测维度不能超过 2 个。")

    if len(payload.prompt) > 160:
        errors.append("题面过长，请控制在 160 字以内。")

    if any(phrase in payload.prompt for phrase in MORALIZING_PHRASES):
        errors.append("题面包含价值判断式措辞。")

    if any(term in payload.prompt for term in SENSITIVE_TERMS):
        errors.append("题面包含敏感主题，不适合进入核心测量。")

    if len(payload.options) < 2:
        errors.append("至少需要 2 个选项。")

    return errors


def validate_generated_prompt(prompt: str) -> list[str]:
    errors: list[str] = []
    if len(prompt) > 160:
        errors.append("改写后的题面过长。")
    if any(phrase in prompt for phrase in MORALIZING_PHRASES):
        errors.append("改写后的题面包含价值判断式措辞。")
    if any(term in prompt for term in SENSITIVE_TERMS):
        errors.append("改写后的题面包含敏感主题。")
    return errors


def validate_likert_prompt(prompt: str) -> list[str]:
    errors = validate_generated_prompt(prompt)
    if any(pattern in prompt for pattern in LIKERT_INCOMPATIBLE_PATTERNS):
        errors.append("题面不适合同意/不同意量表作答。")
    if "还是" in prompt and "我" not in prompt:
        errors.append("题面更像二选一问句，不适合同意量表。")
    if not any(token in prompt for token in ("我", "自己", "通常", "往往")):
        errors.append("题面缺少可对自身进行同意判断的陈述锚点。")
    return errors


def validate_contrast_probe(prompt: str, left_anchor: str, right_anchor: str) -> list[str]:
    errors = validate_generated_prompt(prompt)
    if not prompt:
        errors.append("对照型题面不能为空。")
    if "？" not in prompt and "?" not in prompt and "更接近哪一侧" not in prompt:
        errors.append("对照型题面缺少明确的偏好判断提示。")
    if not left_anchor or not right_anchor:
        errors.append("对照型题面缺少左右锚点。")
    if left_anchor == right_anchor:
        errors.append("左右锚点不能相同。")
    if any(term in left_anchor + right_anchor for term in SENSITIVE_TERMS):
        errors.append("对照型锚点包含敏感主题。")
    return errors
