"""Core dimension definitions for Distilled TI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionDefinition:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class ProbeDimensionDefinition:
    key: str
    label: str
    parent: str
    description: str
    safe_domain: str
    fallback_prompts: tuple[str, ...]
    contrast_pairs: tuple[tuple[str, str], ...]


CORE_DIMENSIONS: tuple[DimensionDefinition, ...] = (
    DimensionDefinition("social_initiative", "社交主动性", "主动开启互动、发起协作、率先表达的倾向。"),
    DimensionDefinition(
        "social_stimulation_tolerance",
        "社交刺激耐受",
        "在高密度互动、噪声和刺激下维持状态的能力。",
    ),
    DimensionDefinition("autonomous_judgment", "自主决断倾向", "偏独立判断还是偏依赖权威、流程、共识。"),
    DimensionDefinition("planning_preference", "规划结构偏好", "对清单、结构化、预先规划的偏好。"),
    DimensionDefinition("risk_tolerance", "风险容忍度", "面对不确定性时承受波动与下注的倾向。"),
    DimensionDefinition("abstraction_tendency", "抽象化倾向", "偏好概念、模型、理论还是实例、经验、操作。"),
    DimensionDefinition("novelty_seeking", "新奇寻求", "对新方法、新环境、新体验的追求程度。"),
    DimensionDefinition("competition_cooperation", "竞争合作取向", "默认驱动更偏竞争领先还是合作共建。"),
    DimensionDefinition("emotional_stability", "情绪稳定性", "受反馈、冲突与扰动影响的强弱和恢复速度。"),
    DimensionDefinition("execution_drive", "推进执行力", "把判断转成推进、落地和收尾的能力倾向。"),
)

CORE_DIMENSION_KEYS: tuple[str, ...] = tuple(definition.key for definition in CORE_DIMENSIONS)
CORE_DIMENSION_LABELS: dict[str, str] = {definition.key: definition.label for definition in CORE_DIMENSIONS}

ITEM_BANK_SUBDIMENSION_TO_PARENT: dict[str, str] = {
    "entry_speed": "social_initiative",
    "familiar_expression_intensity": "social_stimulation_tolerance",
    "conflict_speaking_threshold": "social_initiative",
    "low_info_decision_speed": "autonomous_judgment",
    "authority_dependence": "autonomous_judgment",
    "ambiguity_tolerance": "risk_tolerance",
    "start_speed": "execution_drive",
    "switching_tendency": "planning_preference",
    "closure_strength": "execution_drive",
}

ITEM_BANK_SUBDIMENSION_LABELS: dict[str, str] = {
    "entry_speed": "进入速度",
    "familiar_expression_intensity": "熟人表达强度",
    "conflict_speaking_threshold": "冲突开口阈值",
    "low_info_decision_speed": "低信息决断速度",
    "authority_dependence": "权威依赖度",
    "ambiguity_tolerance": "模糊容忍度",
    "start_speed": "启动速度",
    "switching_tendency": "中途切换倾向",
    "closure_strength": "收尾能力",
}

AI_PROBE_DIMENSIONS: tuple[ProbeDimensionDefinition, ...] = (
    ProbeDimensionDefinition(
        "academic_utility_scope",
        "学科效用边界",
        "abstraction_tendency",
        "判断一门学科是否值得投入时，更看长期解释力还是即时用途。",
        "学术 taste",
        (
            "面对一门短期很难直接变现、但长期解释力很强的学科，我通常仍会觉得它值得认真投入。",
            "如果一门学科短期看不出立刻可用的地方，我也未必会把它判成“没什么用”。",
        ),
        (
            ("更看长期解释力", "更看眼前可用性"),
            ("愿意为长期框架投入", "优先为即时用途投入"),
        ),
    ),
    ProbeDimensionDefinition(
        "theory_application_balance",
        "理论-应用平衡",
        "abstraction_tendency",
        "更容易被能改写理解框架的理论吸引，还是被马上能上手的应用吸引。",
        "知识取向",
        (
            "同样有价值的内容里，我往往更容易被会改写理解框架的理论吸住，而不只是被立刻能用的方法吸住。",
            "如果一个东西能立刻派上用场，但背后框架很薄，我未必会真正喜欢它。",
        ),
        (
            ("偏向理论骨架", "偏向立刻能用"),
            ("先看框架厚度", "先看上手效率"),
        ),
    ),
    ProbeDimensionDefinition(
        "canon_reliance",
        "经典依附度",
        "autonomous_judgment",
        "面对经典、名家或主流推荐时，默认贴近还是默认重审。",
        "学术判断",
        (
            "面对一份被普遍认可的经典书单时，我通常不会只因为它经典就自动接受它的排序。",
            "即使一套观点已经被很多人当成标准入口，我也仍会先判断它是不是我真正认同的入口。",
        ),
        (
            ("先自己重审经典", "先沿经典入口走"),
            ("默认保留怀疑", "默认贴近主流入口"),
        ),
    ),
    ProbeDimensionDefinition(
        "aesthetic_density",
        "审美密度偏好",
        "novelty_seeking",
        "更偏好信息密度高、结构复杂的表达，还是更偏好简洁直接的表达。",
        "表达审美",
        (
            "相比平直清爽的表达，我往往更容易被那种信息密度高、层次很多的表达吸住。",
            "如果一段内容结构复杂但真有层次，我通常不会因为它不够轻巧就立刻失去兴趣。",
        ),
        (
            ("偏好多层复调", "偏好清晰直给"),
            ("更能吃高密度表达", "更喜欢轻巧直接表达"),
        ),
    ),
)

AI_PROBE_DIMENSION_KEYS: tuple[str, ...] = tuple(definition.key for definition in AI_PROBE_DIMENSIONS)
AI_PROBE_DIMENSIONS_BY_KEY: dict[str, ProbeDimensionDefinition] = {
    definition.key: definition for definition in AI_PROBE_DIMENSIONS
}

SUBDIMENSION_TO_PARENT: dict[str, str] = ITEM_BANK_SUBDIMENSION_TO_PARENT | {
    definition.key: definition.parent for definition in AI_PROBE_DIMENSIONS
}

SUBDIMENSION_LABELS: dict[str, str] = ITEM_BANK_SUBDIMENSION_LABELS | {
    definition.key: definition.label for definition in AI_PROBE_DIMENSIONS
}

MODULE_KEYS: tuple[str, ...] = (
    "study_style",
    "project_role",
    "conflict_mode",
    "chat_mode",
    "creative_mode",
    "team_mode",
)

MODULE_LABELS: dict[str, str] = {
    "study_style": "学习协作风格",
    "project_role": "项目组人格",
    "conflict_mode": "冲突处理风格",
    "chat_mode": "网聊人格",
    "creative_mode": "创作人格",
    "team_mode": "队友人格",
}


def make_zero_vector(value: float = 0.0) -> dict[str, float]:
    return {key: value for key in CORE_DIMENSION_KEYS}


def make_zero_subdimension_vector(value: float = 0.0) -> dict[str, float]:
    return {key: value for key in SUBDIMENSION_TO_PARENT}


def make_zero_module_vector(value: float = 0.0) -> dict[str, float]:
    return {key: value for key in MODULE_KEYS}
