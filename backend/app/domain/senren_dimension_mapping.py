"""千恋万花 选择→人格维度映射表

将游戏中每个选择选项映射到 Distilled TI 的 10 个核心维度。
每个选项携带 dimension_weights，用于驱动 ScoringEngine 的状态更新。

设计原则：
- 每个选项主要影响 1-2 个维度（主效应），可能有 0-1 个副效应
- 权重符号：正 = 强化该维度倾向，负 = 弱化
- 关键剧情转折点的选项权重更高（0.8-1.0）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChoiceDimensionMapping:
    """一个选择选项到人格维度的完整映射"""
    choice_id: str              # 对应 GameChoiceNode.choice_id
    option_key: str             # 对应 GameChoiceOption.key
    # 核心维度权重映射
    dimension_weights: dict[str, float]
    # 子维度权重（进阶测量）
    subdimension_weights: dict[str, float]
    # 模块亲和度
    module_affinities: dict[str, float]
    # 情境标签（用于选题策略的去重和多样性）
    scenario_tags: list[str]
    # 该选择的"信息量"（类似 IRT 中的区分度）
    discrimination: float
    # 该选择的"偏置"（类似 IRT 中的难度/阈值）
    difficulty: float


# ============================================================
# 完整的选项→维度映射表
# ============================================================

CHOICE_DIMENSION_MAP: list[ChoiceDimensionMapping] = [
    # ========================================
    # C1: 对小镇的第一印象（芦花）
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c1",
        option_key="honest",
        dimension_weights={"social_initiative": 0.6, "emotional_stability": 0.4},
        subdimension_weights={"entry_speed": 0.6},
        module_affinities={"chat_mode": 0.5},
        scenario_tags=["穗织镇", "芦花", "初次见面", "温泉旅馆"],
        discrimination=0.7,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c1",
        option_key="evade",
        dimension_weights={"social_initiative": -0.4, "risk_tolerance": -0.3},
        subdimension_weights={"entry_speed": -0.4},
        module_affinities={"chat_mode": -0.3},
        scenario_tags=["穗织镇", "芦花", "初次见面", "温泉旅馆"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # ========================================
    # C2: 对乡下生活的看法（茉子）
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c2",
        option_key="hesitant",
        dimension_weights={"novelty_seeking": 0.5, "abstraction_tendency": 0.3},
        subdimension_weights={"ambiguity_tolerance": 0.5},
        module_affinities={"study_style": 0.3},
        scenario_tags=["穗织镇", "茉子", "新环境适应", "街道"],
        discrimination=0.7,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c2",
        option_key="urban_prefer",
        dimension_weights={"novelty_seeking": -0.6, "planning_preference": 0.3},
        subdimension_weights={"ambiguity_tolerance": -0.5},
        module_affinities={},
        scenario_tags=["穗织镇", "茉子", "新环境适应", "街道"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # ========================================
    # C3: 蕾娜的手工艺品
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c3",
        option_key="cute",
        dimension_weights={"emotional_stability": 0.5, "social_initiative": 0.5},
        subdimension_weights={"familiar_expression_intensity": 0.4},
        module_affinities={"chat_mode": 0.6, "team_mode": 0.3},
        scenario_tags=["学校", "蕾娜", "文化差异", "手工"],
        discrimination=0.7,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c3",
        option_key="strange",
        dimension_weights={"autonomous_judgment": 0.4, "social_initiative": -0.3},
        subdimension_weights={},
        module_affinities={"chat_mode": -0.2},
        scenario_tags=["学校", "蕾娜", "文化差异", "手工"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # ========================================
    # C4: 祭典准备——选择帮什么忙
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c4",
        option_key="fishing",
        dimension_weights={"social_initiative": 0.5, "execution_drive": 0.5},
        subdimension_weights={"start_speed": 0.5},
        module_affinities={"team_mode": 0.5, "project_role": 0.4},
        scenario_tags=["志那都神社", "芳乃", "祭典准备", "河边"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c4",
        option_key="herbs",
        dimension_weights={"novelty_seeking": 0.5, "social_initiative": 0.4},
        subdimension_weights={"ambiguity_tolerance": 0.4},
        module_affinities={"team_mode": 0.4, "creative_mode": 0.5},
        scenario_tags=["志那都神社", "茉子", "祭典准备", "山中"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c4",
        option_key="solo",
        dimension_weights={"autonomous_judgment": 0.6, "planning_preference": 0.3},
        subdimension_weights={"authority_dependence": -0.5},
        module_affinities={"project_role": 0.4, "study_style": 0.3},
        scenario_tags=["志那都神社", "丛雨", "祭典准备", "独处"],
        discrimination=0.8,
        difficulty=0.0,
    ),

    # ========================================
    # C4a: 钓鱼后的分支——怎么回应芳乃
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c4a",
        option_key="insist",
        dimension_weights={"emotional_stability": 0.5, "autonomous_judgment": 0.5},
        subdimension_weights={"conflict_speaking_threshold": 0.6},
        module_affinities={"conflict_mode": 0.5, "team_mode": 0.4},
        scenario_tags=["河边", "芳乃", "夕阳", "关心"],
        discrimination=0.85,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c4a",
        option_key="accept",
        dimension_weights={"social_initiative": 0.5, "competition_cooperation": -0.3},
        subdimension_weights={"authority_dependence": 0.4},
        module_affinities={"team_mode": 0.6, "chat_mode": 0.3},
        scenario_tags=["河边", "蕾娜", "夕阳", "妥协"],
        discrimination=0.85,
        difficulty=0.0,
    ),

    # ========================================
    # C5: 面对丛雨——如何回应她的脆弱
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c5",
        option_key="words",
        dimension_weights={"abstraction_tendency": 0.5, "autonomous_judgment": 0.4},
        subdimension_weights={"low_info_decision_speed": 0.3},
        module_affinities={"chat_mode": 0.4},
        scenario_tags=["神社", "丛雨", "古树", "神话", "感谢"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c5",
        option_key="pat_head",
        dimension_weights={"social_initiative": 0.7, "emotional_stability": 0.3},
        subdimension_weights={"familiar_expression_intensity": 0.6},
        module_affinities={"chat_mode": 0.6, "team_mode": 0.3},
        scenario_tags=["神社", "丛雨", "古树", "触碰", "安慰"],
        discrimination=0.85,
        difficulty=0.0,
    ),

    # ========================================
    # C6: 小春的秘密
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c6",
        option_key="worry",
        dimension_weights={"execution_drive": 0.5, "social_initiative": 0.4},
        subdimension_weights={"start_speed": 0.5},
        module_affinities={"team_mode": 0.5},
        scenario_tags=["学校", "小春", "弓道场", "担心", "秘密"],
        discrimination=0.7,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c6",
        option_key="trust",
        dimension_weights={"autonomous_judgment": -0.4, "emotional_stability": 0.5},
        subdimension_weights={"authority_dependence": -0.4},
        module_affinities={"chat_mode": 0.4},
        scenario_tags=["学校", "小春", "弓道场", "信任"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # ========================================
    # C7: 祭典前夜——面对焦虑的芳乃
    # ========================================
    ChoiceDimensionMapping(
        choice_id="senren-c7",
        option_key="comfort",
        dimension_weights={"emotional_stability": 0.5, "social_initiative": 0.6},
        subdimension_weights={"conflict_speaking_threshold": 0.6},
        module_affinities={"conflict_mode": 0.5, "chat_mode": 0.6},
        scenario_tags=["朝武家", "芳乃", "祭典前夜", "焦虑", "支持"],
        discrimination=0.9,
        difficulty=0.1,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-c7",
        option_key="silent",
        dimension_weights={"autonomous_judgment": 0.4, "risk_tolerance": -0.3},
        subdimension_weights={"ambiguity_tolerance": -0.3},
        module_affinities={"conflict_mode": -0.3},
        scenario_tags=["朝武家", "芳乃", "祭典前夜", "沉默", "陪伴"],
        discrimination=0.8,
        difficulty=0.1,
    ),
]

# ============================================================
# 扩展情境选择（非游戏原文但基于游戏世界观的心理测量场景）
# ============================================================

EXPANDED_SCENARIOS: list[ChoiceDimensionMapping] = [
    # === 社交主动性 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-social-1",
        option_key="approach",
        dimension_weights={"social_initiative": 0.8, "emotional_stability": 0.2},
        subdimension_weights={"entry_speed": 0.8},
        module_affinities={"chat_mode": 0.5},
        scenario_tags=["穗织镇", "神社", "陌生人", "搭话"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-social-2",
        option_key="lead",
        dimension_weights={"social_initiative": 0.7, "execution_drive": 0.3},
        subdimension_weights={"conflict_speaking_threshold": 0.5},
        module_affinities={"team_mode": 0.6},
        scenario_tags=["祭典", "群体", "领导", "组织"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-social-3",
        option_key="join",
        dimension_weights={"social_initiative": 0.6, "novelty_seeking": 0.4},
        subdimension_weights={"entry_speed": 0.5},
        module_affinities={"team_mode": 0.5, "chat_mode": 0.4},
        scenario_tags=["学校", "社团", "新人", "融入"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # === 社交刺激耐受 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-stim-1",
        option_key="calm",
        dimension_weights={"social_stimulation_tolerance": 0.8, "emotional_stability": 0.2},
        subdimension_weights={"familiar_expression_intensity": 0.3},
        module_affinities={"team_mode": 0.5},
        scenario_tags=["祭典", "人群", "混乱", "多任务"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-stim-2",
        option_key="focus",
        dimension_weights={"social_stimulation_tolerance": 0.6, "execution_drive": 0.3},
        subdimension_weights={},
        module_affinities={"project_role": 0.4},
        scenario_tags=["旅馆", "游客", "嘈杂", "专注"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # === 自主决断倾向 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-decision-1",
        option_key="challenge",
        dimension_weights={"autonomous_judgment": 0.8, "risk_tolerance": 0.2},
        subdimension_weights={"authority_dependence": -0.7},
        module_affinities={"conflict_mode": 0.5},
        scenario_tags=["神社", "长老", "传统", "质疑"],
        discrimination=0.85,
        difficulty=0.1,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-decision-2",
        option_key="follow",
        dimension_weights={"autonomous_judgment": -0.6, "planning_preference": 0.4},
        subdimension_weights={"authority_dependence": 0.7},
        module_affinities={"team_mode": 0.4},
        scenario_tags=["神社", "长老", "传统", "遵从"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-decision-3",
        option_key="weigh",
        dimension_weights={"autonomous_judgment": 0.5, "abstraction_tendency": 0.4},
        subdimension_weights={"low_info_decision_speed": 0.5},
        module_affinities={"study_style": 0.5},
        scenario_tags=["图书馆", "研究", "诅咒", "分析"],
        discrimination=0.75,
        difficulty=0.0,
    ),

    # === 规划结构偏好 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-plan-1",
        option_key="schedule",
        dimension_weights={"planning_preference": 0.8, "execution_drive": 0.2},
        subdimension_weights={"start_speed": 0.3},
        module_affinities={"project_role": 0.6},
        scenario_tags=["祭典", "准备", "清单", "时间表"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-plan-2",
        option_key="improvise",
        dimension_weights={"planning_preference": -0.7, "risk_tolerance": 0.4},
        subdimension_weights={"ambiguity_tolerance": 0.5},
        module_affinities={"creative_mode": 0.6},
        scenario_tags=["祭典", "即兴", "灵活", "应变"],
        discrimination=0.75,
        difficulty=0.0,
    ),

    # === 风险容忍度 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-risk-1",
        option_key="reckless",
        dimension_weights={"risk_tolerance": 0.8, "novelty_seeking": 0.3},
        subdimension_weights={"ambiguity_tolerance": 0.6},
        module_affinities={"creative_mode": 0.5},
        scenario_tags=["神社", "禁地", "探索", "未知"],
        discrimination=0.85,
        difficulty=0.1,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-risk-2",
        option_key="cautious",
        dimension_weights={"risk_tolerance": -0.7, "planning_preference": 0.4},
        subdimension_weights={"ambiguity_tolerance": -0.6},
        module_affinities={"project_role": 0.4},
        scenario_tags=["神社", "禁地", "谨慎", "安全"],
        discrimination=0.8,
        difficulty=0.0,
    ),

    # === 抽象化倾向 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-abstract-1",
        option_key="meaning",
        dimension_weights={"abstraction_tendency": 0.8, "novelty_seeking": 0.2},
        subdimension_weights={},
        module_affinities={"study_style": 0.6},
        scenario_tags=["神社", "神话", "解读", "象征"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-abstract-2",
        option_key="practical",
        dimension_weights={"abstraction_tendency": -0.6, "execution_drive": 0.4},
        subdimension_weights={},
        module_affinities={"project_role": 0.5},
        scenario_tags=["祭典", "务实", "执行", "行动"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # === 新奇寻求 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-novelty-1",
        option_key="explore",
        dimension_weights={"novelty_seeking": 0.8, "risk_tolerance": 0.2},
        subdimension_weights={"ambiguity_tolerance": 0.4},
        module_affinities={"creative_mode": 0.5},
        scenario_tags=["穗织镇", "探索", "古迹", "新奇"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-novelty-2",
        option_key="routine",
        dimension_weights={"novelty_seeking": -0.6, "planning_preference": 0.3},
        subdimension_weights={},
        module_affinities={},
        scenario_tags=["穗织镇", "习惯", "日常", "熟悉"],
        discrimination=0.7,
        difficulty=0.0,
    ),

    # === 竞争—合作取向 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-compete-1",
        option_key="compete",
        dimension_weights={"competition_cooperation": 0.8, "execution_drive": 0.2},
        subdimension_weights={"start_speed": 0.3},
        module_affinities={"team_mode": 0.3},
        scenario_tags=["剑道", "比赛", "胜负", "对手"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-compete-2",
        option_key="cooperate",
        dimension_weights={"competition_cooperation": -0.7, "social_initiative": 0.3},
        subdimension_weights={},
        module_affinities={"team_mode": 0.7},
        scenario_tags=["剑道", "合作", "练习", "伙伴"],
        discrimination=0.8,
        difficulty=0.0,
    ),

    # === 情绪稳定性 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-emotion-1",
        option_key="steady",
        dimension_weights={"emotional_stability": 0.8, "autonomous_judgment": 0.2},
        subdimension_weights={"conflict_speaking_threshold": 0.4},
        module_affinities={"conflict_mode": 0.7},
        scenario_tags=["朝武家", "冲突", "压力", "冷静"],
        discrimination=0.85,
        difficulty=0.1,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-emotion-2",
        option_key="shaken",
        dimension_weights={"emotional_stability": -0.7, "social_stimulation_tolerance": -0.3},
        subdimension_weights={},
        module_affinities={"conflict_mode": -0.5},
        scenario_tags=["朝武家", "冲突", "压力", "动摇"],
        discrimination=0.8,
        difficulty=0.0,
    ),

    # === 推进执行力 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-exec-1",
        option_key="act",
        dimension_weights={"execution_drive": 0.8, "risk_tolerance": 0.2},
        subdimension_weights={"start_speed": 0.8},
        module_affinities={"project_role": 0.6},
        scenario_tags=["祭典", "危机", "行动", "决断"],
        discrimination=0.85,
        difficulty=0.1,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-exec-2",
        option_key="wait",
        dimension_weights={"execution_drive": -0.5, "autonomous_judgment": 0.3},
        subdimension_weights={"start_speed": -0.5},
        module_affinities={},
        scenario_tags=["祭典", "等待", "观望", "谨慎"],
        discrimination=0.75,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-exec-3",
        option_key="closure",
        dimension_weights={"execution_drive": 0.7, "planning_preference": 0.3},
        subdimension_weights={"closure_strength": 0.7},
        module_affinities={"project_role": 0.5},
        scenario_tags=["旅馆", "收尾", "完成", "整理"],
        discrimination=0.75,
        difficulty=0.0,
    ),

    # === 交叉维度场景 ===
    ChoiceDimensionMapping(
        choice_id="senren-ext-cross-1",
        option_key="confront",
        dimension_weights={"social_initiative": 0.5, "emotional_stability": 0.5},
        subdimension_weights={"conflict_speaking_threshold": 0.7},
        module_affinities={"conflict_mode": 0.8},
        scenario_tags=["神社", "对峙", "正义", "守护"],
        discrimination=0.85,
        difficulty=0.15,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-cross-2",
        option_key="evade_conflict",
        dimension_weights={"social_initiative": -0.4, "emotional_stability": -0.3},
        subdimension_weights={"conflict_speaking_threshold": -0.6},
        module_affinities={"conflict_mode": -0.5},
        scenario_tags=["神社", "回避", "和平", "退让"],
        discrimination=0.8,
        difficulty=0.0,
    ),
    ChoiceDimensionMapping(
        choice_id="senren-ext-cross-3",
        option_key="investigate",
        dimension_weights={"abstraction_tendency": 0.5, "novelty_seeking": 0.4},
        subdimension_weights={"low_info_decision_speed": 0.5},
        module_affinities={"study_style": 0.7},
        scenario_tags=["图书馆", "调查", "诅咒", "研究"],
        discrimination=0.8,
        difficulty=0.0,
    ),
]

# ============================================================
# 角色维度画像（用于角色契合度计算）
# ============================================================

CHARACTER_PROFILES: dict[str, dict[str, float]] = {
    "芳乃": {
        "social_initiative": -0.3,
        "social_stimulation_tolerance": 0.0,
        "planning_preference": 0.8,
        "autonomous_judgment": 0.2,
        "execution_drive": 0.6,
        "emotional_stability": 0.1,
        "risk_tolerance": -0.2,
        "competition_cooperation": -0.1,
        "abstraction_tendency": 0.3,
        "novelty_seeking": -0.4,
    },
    "丛雨": {
        "social_initiative": 0.5,
        "social_stimulation_tolerance": 0.3,
        "planning_preference": -0.2,
        "autonomous_judgment": 0.5,
        "execution_drive": 0.1,
        "emotional_stability": 0.4,
        "risk_tolerance": 0.3,
        "competition_cooperation": -0.3,
        "abstraction_tendency": 0.5,
        "novelty_seeking": 0.7,
    },
    "茉子": {
        "social_initiative": 0.6,
        "social_stimulation_tolerance": 0.2,
        "planning_preference": -0.4,
        "autonomous_judgment": 0.6,
        "execution_drive": 0.2,
        "emotional_stability": -0.2,
        "risk_tolerance": 0.5,
        "competition_cooperation": 0.0,
        "abstraction_tendency": 0.0,
        "novelty_seeking": 0.4,
    },
    "蕾娜": {
        "social_initiative": 0.8,
        "social_stimulation_tolerance": 0.6,
        "planning_preference": -0.3,
        "autonomous_judgment": -0.1,
        "execution_drive": 0.1,
        "emotional_stability": 0.5,
        "risk_tolerance": 0.4,
        "competition_cooperation": -0.8,
        "abstraction_tendency": -0.5,
        "novelty_seeking": 0.9,
    },
    "小春": {
        "social_initiative": 0.1,
        "social_stimulation_tolerance": 0.4,
        "planning_preference": 0.5,
        "autonomous_judgment": 0.6,
        "execution_drive": 0.7,
        "emotional_stability": 0.5,
        "risk_tolerance": 0.0,
        "competition_cooperation": 0.3,
        "abstraction_tendency": 0.2,
        "novelty_seeking": -0.1,
    },
    "芦花": {
        "social_initiative": 0.7,
        "social_stimulation_tolerance": 0.5,
        "planning_preference": 0.3,
        "autonomous_judgment": 0.1,
        "execution_drive": 0.3,
        "emotional_stability": 0.6,
        "risk_tolerance": 0.1,
        "competition_cooperation": -0.6,
        "abstraction_tendency": -0.3,
        "novelty_seeking": 0.2,
    },
    "将臣": {
        "social_initiative": 0.2,
        "social_stimulation_tolerance": 0.3,
        "planning_preference": 0.1,
        "autonomous_judgment": 0.4,
        "execution_drive": 0.3,
        "emotional_stability": 0.5,
        "risk_tolerance": 0.1,
        "competition_cooperation": -0.3,
        "abstraction_tendency": 0.0,
        "novelty_seeking": 0.2,
    },
    "廉太郎": {
        "social_initiative": 0.6,
        "social_stimulation_tolerance": 0.1,
        "planning_preference": -0.5,
        "autonomous_judgment": -0.2,
        "execution_drive": 0.4,
        "emotional_stability": -0.4,
        "risk_tolerance": 0.3,
        "competition_cooperation": 0.2,
        "abstraction_tendency": -0.6,
        "novelty_seeking": 0.5,
    },
    "隆文": {
        "social_initiative": -0.6,
        "social_stimulation_tolerance": -0.3,
        "planning_preference": 0.9,
        "autonomous_judgment": 0.7,
        "execution_drive": 0.5,
        "emotional_stability": 0.7,
        "risk_tolerance": -0.6,
        "competition_cooperation": 0.4,
        "abstraction_tendency": 0.5,
        "novelty_seeking": -0.7,
    },
}


# ============================================================
# 辅助函数
# ============================================================

def get_mapping_for_choice(choice_id: str) -> list[ChoiceDimensionMapping]:
    """返回某个选择节点的所有选项映射"""
    return [m for m in CHOICE_DIMENSION_MAP if m.choice_id == choice_id]


def get_mapping(choice_id: str, option_key: str) -> ChoiceDimensionMapping | None:
    """查找特定选择选项的维度映射"""
    for m in CHOICE_DIMENSION_MAP + EXPANDED_SCENARIOS:
        if m.choice_id == choice_id and m.option_key == option_key:
            return m
    return None


def get_all_mappings() -> list[ChoiceDimensionMapping]:
    """返回所有映射（游戏原文 + 扩展场景）"""
    return CHOICE_DIMENSION_MAP + EXPANDED_SCENARIOS


def count_total_options() -> int:
    """统计总选项数"""
    return len(get_all_mappings())


def compute_character_affinity(
    user_core_mu: dict[str, float],
) -> dict[str, float]:
    """计算用户与各角色的契合度（余弦相似度 × 100）"""
    import math

    results = {}
    for name, profile in CHARACTER_PROFILES.items():
        dot = sum(user_core_mu.get(k, 0.0) * profile.get(k, 0.0) for k in profile)
        norm_user = math.sqrt(sum(v ** 2 for v in user_core_mu.values()))
        norm_char = math.sqrt(sum(v ** 2 for v in profile.values()))
        if norm_user > 0 and norm_char > 0:
            similarity = dot / (norm_user * norm_char)
        else:
            similarity = 0.0
        results[name] = round(max(0.0, similarity) * 100, 1)
    return dict(sorted(results.items(), key=lambda x: x[1], reverse=True))
