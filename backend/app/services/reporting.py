"""Stable rule layer for narrative labels and fine-grained insights."""

from __future__ import annotations

from collections.abc import Callable

from app.domain.dimensions import CORE_DIMENSION_LABELS, MODULE_LABELS, SUBDIMENSION_LABELS, SUBDIMENSION_TO_PARENT
from app.domain.models import ModuleInsight, SessionState, SubdimensionInsight


def render_narrative_label(state: SessionState, cluster_name: str) -> str:
    top_core = sorted(state.core_mu.items(), key=lambda item: abs(item[1]), reverse=True)[:3]
    leaders = {key for key, _score in top_core}
    if {"planning_preference", "execution_drive"} <= leaders:
        return "先铺轨再发车的调度盘"
    if {"abstraction_tendency", "novelty_seeking"} & leaders and "autonomous_judgment" in leaders:
        return "会自己改写航线的星图"
    if {"social_initiative", "novelty_seeking"} <= leaders:
        return "边扩张边试探的天线"
    if {"emotional_stability", "planning_preference"} <= leaders:
        return "低摆幅的稳压器"
    if "risk_tolerance" in leaders and "autonomous_judgment" in leaders:
        return "在雾里校准方向的罗盘"
    return f"{cluster_name}里的游移结构体"


SUB_RULES: dict[str, tuple[str, str, str, str, str, str]] = {
    "entry_speed": ("起步偏快", "进入新场面时你通常会先伸手试温。", "像一根先探出去的触角", "起步偏慢", "你更像先观察出入口，再决定何时入场。", "像收着的折叠刀"),
    "familiar_expression_intensity": ("熟场升温明显", "在熟人环境里，你的表达会明显加码。", "像回到高频段的音箱", "熟场波动不大", "熟人也未必会显著放大你的表达强度。", "像稳住电平的混音台"),
    "conflict_speaking_threshold": ("开口阈值较低", "分歧一旦成形，你通常较早出声。", "像较早点亮的警示灯", "开口阈值较高", "你更倾向等分歧真正逼近核心再开口。", "像延迟触发的保险栓"),
    "low_info_decision_speed": ("低信息决断偏快", "信息不全也不太会卡住你往前走。", "像能边跑边校的陀螺", "低信息决断偏慢", "你更倾向把关键缺口补到位再做决定。", "像反复校零的天平"),
    "authority_dependence": ("权威依赖偏低", "已有标准答案时，你仍保留较强的自校机制。", "像不完全跟随信标的船", "权威依赖偏高", "有权威坐标时，你更容易把它作为主轴。", "像贴着轨道走的车厢"),
    "ambiguity_tolerance": ("模糊容忍较高", "不完整状态不会立刻打断你的推进。", "像在雾里还能稳步滑行的滑板", "模糊容忍较低", "你更喜欢先把边界照亮，再继续往前。", "像需要清晰刻度的量尺"),
    "start_speed": ("启动速度较快", "从想法到第一步的跨越对你来说并不算重。", "像一按就弹开的簧片", "启动速度较慢", "你更像先聚拢能量，再迈出真正那一步。", "像预热较久的引擎"),
    "switching_tendency": ("切轨倾向较低", "已经跑起来的计划不容易被新想法拽走。", "像咬住轨道的列车轮", "切轨倾向较高", "新路径一出现，很容易重新吸走你的注意力。", "像随风转向的纸鸢"),
    "closure_strength": ("收尾强度较高", "你会把已开工的事尽量收成一个完整面。", "像会自己扣合的卡榫", "收尾强度较低", "你更擅长启动和铺开，收尾未必是第一驱动。", "像前端锋利的拆封刀"),
    "academic_utility_scope": ("长期效用视野更强", "判断学科价值时，你不只盯眼前用途，也会看它能否长期改写理解结构。", "像看远处地形的测绘镜", "即时效用权重更高", "你更容易先用眼前可用性来判断一门学科值不值得投入。", "像先测落地半径的尺规"),
    "theory_application_balance": ("理论牵引更强", "你更容易被能改写框架的理论吸住，而不只是被立刻能用的方法吸住。", "像先看骨架的解剖灯", "应用牵引更强", "你更容易优先认同那些能立刻落手的工具和路径。", "像先摸得到扳手的工具箱"),
    "canon_reliance": ("经典依附较低", "即使面对公认入口，你也保留较强的重审和自校机制。", "像会自己校准刻度的罗盘", "经典依附较高", "有成熟书单或主流入口时，你更愿意先贴着它们走。", "像先沿主航道行进的船"),
    "aesthetic_density": ("审美密度偏高", "信息密度高、结构层次多的表达更容易抓住你。", "像会被复调吸住的耳朵", "审美密度偏低", "你更偏好简洁、直接、阻力更小的表达。", "像先清掉噪声的滤波器"),
}

MODULE_RULES: dict[str, tuple[str, str]] = {
    "study_style": ("你在学习协作里更像会自动分工的白板。", "学习协作时会自然去拆解角色和节奏。"),
    "project_role": ("项目推进时你像一块会重新排线的主板。", "更容易在项目里承担调度、接线或推进功能。"),
    "conflict_mode": ("处理分歧时你像先找断点的检修夹。", "冲突里更偏定位问题而不是立刻争胜负。"),
    "chat_mode": ("网聊状态像会自动换挡的拨片。", "对话节奏变化时切换模式较快。"),
    "creative_mode": ("创作时像会边生长边校准的枝杈。", "更容易在成形之前持续试探方向。"),
    "team_mode": ("组队时像会读场面的阵型板。", "会较快判断队伍该冲、该拆还是该稳。"),
}


def _confidence_percent(sample_count: int, sigma: float) -> float:
    sample_term = min(sample_count / 4, 1.0) * 55
    sigma_term = max(0.0, min((1.6 - sigma) / 0.9, 1.0)) * 45
    return round(min(100.0, sample_term + sigma_term), 1)


def _confidence_label(confidence_percent: float) -> str:
    if confidence_percent >= 75:
        return "较稳定"
    if confidence_percent >= 45:
        return "成形中"
    return "试探态"


def _direction_label(score: float) -> str:
    if score >= 0.45:
        return "明显偏高"
    if score >= 0.12:
        return "略偏高"
    if score <= -0.45:
        return "明显偏低"
    if score <= -0.12:
        return "略偏低"
    return "居中摇摆"


def _strength_label(score: float) -> str:
    magnitude = abs(score)
    if magnitude >= 0.7:
        return "强信号"
    if magnitude >= 0.35:
        return "中信号"
    return "弱信号"


def build_subdimension_insights(state: SessionState, to_percent: Callable[[float], float]) -> list[SubdimensionInsight]:
    keys = list(state.unlocked_subdimensions)
    if not keys:
        ranked = sorted(
            state.sub_mu.items(),
            key=lambda item: (state.sub_counts.get(item[0], 0), abs(item[1])),
            reverse=True,
        )
        keys = [
            key
            for key, value in ranked
            if state.sub_counts.get(key, 0) > 0 or abs(value) >= 0.08
        ][:4]

    insights: list[SubdimensionInsight] = []
    for key in keys:
        score = state.sub_mu.get(key, 0.0)
        sigma = state.sub_sigma.get(key, 1.5)
        sample_count = state.sub_counts.get(key, 0)
        confidence_percent = _confidence_percent(sample_count, sigma)
        parent = SUBDIMENSION_TO_PARENT[key]
        high_label, high_eval, high_meta, low_label, low_eval, low_meta = SUB_RULES[key]
        direction_label = _direction_label(score)
        strength_label = _strength_label(score)
        if score > 0.12:
            evaluation = f"{high_label}。{high_eval}"
            metaphor = high_meta
        elif score < -0.12:
            evaluation = f"{low_label}。{low_eval}"
            metaphor = low_meta
        else:
            evaluation = "还在中段摆动。你在这个细分上的倾向已经开始出现，但暂时没有完全倒向某一侧。"
            metaphor = "像悬在刻度中央的游标"
        insights.append(
            SubdimensionInsight(
                key=key,
                label=SUBDIMENSION_LABELS[key],
                parent_dimension=parent,
                parent_label=CORE_DIMENSION_LABELS[parent],
                score=round(score, 3),
                percent=to_percent(score),
                sigma=round(sigma, 3),
                sample_count=sample_count,
                confidence_percent=confidence_percent,
                confidence_label=_confidence_label(confidence_percent),
                direction_label=direction_label,
                strength_label=strength_label,
                evaluation=evaluation,
                metaphor=metaphor,
            )
        )
    return sorted(
        insights,
        key=lambda item: (item.sample_count, item.confidence_percent, abs(item.score)),
        reverse=True,
    )


def build_module_insights(state: SessionState, to_percent: Callable[[float], float]) -> list[ModuleInsight]:
    keys = list(state.active_modules)
    if not keys:
        ranked = sorted(
            state.module_scores.items(),
            key=lambda item: (state.module_counts.get(item[0], 0), abs(item[1])),
            reverse=True,
        )
        keys = [
            key
            for key, value in ranked
            if state.module_counts.get(key, 0) > 0 or abs(value) >= 0.1
        ][:3]

    insights: list[ModuleInsight] = []
    for key in keys:
        metaphor, evaluation = MODULE_RULES.get(key, ("像一块临时拼出来的构件。", "该模块已有可见投影。"))
        score = state.module_scores.get(key, 0.0)
        sample_count = state.module_counts.get(key, 0)
        confidence_percent = _confidence_percent(sample_count, max(0.7, 1.35 - abs(score)))
        insights.append(
            ModuleInsight(
                key=key,
                label=MODULE_LABELS[key],
                score=round(score, 3),
                percent=to_percent(score),
                sample_count=sample_count,
                confidence_percent=confidence_percent,
                confidence_label=_confidence_label(confidence_percent),
                strength_label=_strength_label(score),
                evaluation=evaluation,
                metaphor=metaphor,
            )
        )
    return sorted(
        insights,
        key=lambda item: (item.sample_count, item.confidence_percent, abs(item.score)),
        reverse=True,
    )
