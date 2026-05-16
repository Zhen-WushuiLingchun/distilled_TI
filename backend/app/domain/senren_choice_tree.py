"""千恋万花 游戏选择分支树

完整记录游戏中的关键选择点、选项及其所在路线。
数据来源：千恋万花官方攻略、社区流程图。

结构：
- common: 共通线（7个选择节点，所有路线共享前4章）
- routes: 各角色路线（进入个人线后无关键分支，但记录个人线专属情境）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameChoiceOption:
    """单个选择选项"""
    key: str           # 选项标识: "honest" / "evade" / "fishing" ...
    text: str          # 显示文本（中文）
    affection_target: str  # 增加好感度的角色（"芦花"/"茉子"/"芳乃"/"丛雨"/"蕾娜"/"小春"/"none"）


@dataclass(frozen=True)
class GameChoiceNode:
    """游戏中的一个选择点"""
    choice_id: str              # "senren-c1" ~ "senren-c7"
    chapter: str                # "共通线-第1章" ~ "共通线-第7章"
    location: str               # 发生地点
    characters: list[str]       # 相关角色
    context: str                # 剧情上下文描述
    prompt: str                 # 选择提示语（游戏内原文或近似）
    options: list[GameChoiceOption]  # 可选项
    route_tags: list[str]       # 所属路线标签: ["共通线"] / ["芳乃线"] / ...


# ============================================================
# 共通线 7 大选择节点
# ============================================================

COMMON_CHOICES: list[GameChoiceNode] = [
    GameChoiceNode(
        choice_id="senren-c1",
        chapter="共通线-第1章",
        location="穗织镇·温泉旅馆",
        characters=["将臣", "芦花"],
        context="刚来到穗织镇的温泉旅馆，芦花热情地迎接你并询问你对小镇的第一印象。这座被群山环抱、充满乡土气息的小镇与你熟悉的城市截然不同。",
        prompt="你觉得这里怎么样？",
        options=[
            GameChoiceOption("honest", "说实话——这里让人很放松，感觉很舒服", "芦花"),
            GameChoiceOption("evade", "敷衍过去——还行吧，和普通乡下差不多", "none"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c2",
        chapter="共通线-第1章",
        location="穗织镇·街道",
        characters=["将臣", "茉子"],
        context="茉子带你参观小镇，走过古老的石阶和鸟居。她似乎对这个小镇有着复杂的感情，既守护着它又带着某种疏离感。她不经意地问起你对这里生活方式的看法。",
        prompt="你觉得乡下的生活怎么样？",
        options=[
            GameChoiceOption("hesitant", "不好说——可能还需要时间适应，但有很多城市里没有的东西", "茉子"),
            GameChoiceOption("urban_prefer", "还是觉得城市好——这里的节奏太慢了", "none"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c3",
        chapter="共通线-第2章",
        location="穗织镇·学校",
        characters=["将臣", "蕾娜"],
        context="蕾娜兴奋地向你展示她刚学到的日本传统手工艺——一个歪歪扭扭但充满心意的小饰品。她的眼睛里闪烁着期待的光芒，但又带着一丝不安，担心自己的作品在别人看来很奇怪。",
        prompt="你觉得这个手工艺品怎么样？",
        options=[
            GameChoiceOption("cute", "我觉得很可爱——能感受到心意最重要", "蕾娜"),
            GameChoiceOption("strange", "看着不奇怪——但还有进步空间", "none"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c4",
        chapter="共通线-第3章",
        location="穗织镇·志那都神社周边",
        characters=["将臣", "芳乃", "茉子", "丛雨"],
        context="祭典准备进入关键阶段，但人手不足。神社周围摆满了需要分拣的祭具、需要清洗的布料，还有需要去山里采集的特殊草药。几个女孩都在各自忙碌，你决定加入帮忙。",
        prompt="你要选择做什么？",
        options=[
            GameChoiceOption("fishing", "去河边钓鱼——为祭典后的宴会准备食材", "芳乃"),
            GameChoiceOption("herbs", "去山上挖野菜——为祭典料理做准备", "茉子"),
            GameChoiceOption("solo", "单独行动——去打扫神社的角落", "丛雨"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c4a",
        chapter="共通线-第3章（钓鱼分支后续）",
        location="穗织镇·河边",
        characters=["将臣", "芳乃", "蕾娜"],
        context="你和芳乃来到河边钓鱼。夕阳西下，水面波光粼粼。芳乃放下警惕，露出了她难得的柔软一面。蕾娜随后也跑了过来，兴奋地想要一起钓鱼。芳乃的表情突然变得有些微妙。",
        prompt="你要怎么回应芳乃的提议（让她回去休息）？",
        options=[
            GameChoiceOption("insist", "就是不行——你看起来很累，我帮你做就好", "芳乃"),
            GameChoiceOption("accept", "既然你都这么说了——那就一起吧", "蕾娜"),
        ],
        route_tags=["共通线", "芳乃线", "蕾娜线"],
    ),
    GameChoiceNode(
        choice_id="senren-c5",
        chapter="共通线-第5章",
        location="穗织镇·神社",
        characters=["将臣", "丛雨"],
        context="丛雨独自站在神社的古树下，看起来比平时更加脆弱和透明。她刚刚透露了一些关于自己存在的秘密——关于诅咒、关于她作为'ムラサメ'背负的命运。她自嘲地笑了笑，像是在等待审判。",
        prompt="你想说什么来回应她？",
        options=[
            GameChoiceOption("words", "用语言表达谢意——'谢谢你一直守护着大家'", "none"),
            GameChoiceOption("pat_head", "摸摸头——什么都不说，只是轻轻摸了摸她的头", "丛雨"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c6",
        chapter="共通线-第6章",
        location="穗织镇·学校",
        characters=["将臣", "小春"],
        context="小春最近行为有些古怪——她总是偷偷摸摸地在放学后留在弓道场，不知道在做什么。有传言说她卷入了什么麻烦事。小春来找你，眼神躲闪，但语气异常坚定地说她没问题的。",
        prompt="你怎么看待这件事？",
        options=[
            GameChoiceOption("worry", "有点担心——追问她到底发生了什么", "none"),
            GameChoiceOption("trust", "相信小春说的话——但如果需要帮助随时可以说", "小春"),
        ],
        route_tags=["共通线"],
    ),
    GameChoiceNode(
        choice_id="senren-c7",
        chapter="共通线-第7章",
        location="穗织镇·朝武家",
        characters=["将臣", "芳乃"],
        context="芳乃在祭典前夜显得异常焦虑。作为朝武家的继承者，她背负着解开诅咒的重任。今晚她看起来比任何时候都要脆弱，双手紧握，指节发白。她低声说：'如果……如果失败了怎么办？'",
        prompt="你怎么回应？",
        options=[
            GameChoiceOption("comfort", "安抚朝武——'无论发生什么，我都站在你这边'", "芳乃"),
            GameChoiceOption("silent", "还是别说多余的话——静静地陪在她身边", "none"),
        ],
        route_tags=["共通线"],
    ),
]


# ============================================================
# 角色个人线（共通线后的关键差异点）
# ============================================================

# 芳乃线 - 共通线选择导向芳乃好感度≥2 + c7选"安抚朝武"
YOSHINO_ROUTE = {
    "route_name": "朝武芳乃线",
    "route_id": "yoshino",
    "entry_conditions": [
        "c4 选择'钓鱼'",
        "c4a 选择'就是不行'",
        "c7 选择'安抚朝武'",
    ],
    "description": "芳乃作为朝武家的继承者，背负着解开五百年前诅咒的宿命。在这条路线中，你将成为她最重要的支撑，与她一起面对诅咒的真相。这是一条关于信任、责任与羁绊的路线。",
    "key_personality_traits": {
        "social_initiative": "中等偏高——愿意主动靠近但不过分强势",
        "emotional_stability": "高——能在压力情境下提供情感支持",
        "autonomous_judgment": "中高——有自己的判断，不盲从传统",
        "execution_drive": "高——关键时能转化为行动",
        "risk_tolerance": "中——愿意尝试打破诅咒但谨畏后果",
    },
    "character_personality_profile": {
        "芳乃": {
            "social_initiative": -0.3,  # 内向，不主动
            "emotional_stability": 0.0,  # 中等
            "planning_preference": 0.8,  # 喜欢按计划行事
            "autonomous_judgment": 0.2,  # 略独立
            "execution_drive": 0.6,      # 执行力强（剑术）
        },
    },
}

# 丛雨线 - 共通线选择导向丛雨好感度≥2 + c5选"摸摸头"
MURASAME_ROUTE = {
    "route_name": "丛雨（幼刀）线",
    "route_id": "murasame",
    "entry_conditions": [
        "c4 选择'单独行动'",
        "c5 选择'摸摸头'",
    ],
    "description": "丛雨是寄宿在神刀'ムラサメ'中的付丧神。五百年来她独自守护着穗织镇，直到遇见你。这条路线探讨的是孤独、存在意义与被看见的渴望。你帮助她找到作为'丛雨'而非'ムラサメ'的存在方式。",
    "key_personality_traits": {
        "social_initiative": "中——需要主动接近一个习惯了孤独的存在",
        "abstraction_tendency": "偏高——需要理解神话、象征和存在的意义",
        "emotional_stability": "中——面对非人存在的复杂情感",
        "novelty_seeking": "偏高——接受超自然存在的世界观",
    },
    "character_personality_profile": {
        "丛雨": {
            "social_initiative": 0.5,    # 嘴硬但实际很爱说话
            "emotional_stability": 0.4,  # 经历了很多事
            "novelty_seeking": 0.7,      # 对新鲜事物充满好奇
            "abstraction_tendency": 0.5, # 思考存在意义
            "competition_cooperation": -0.3,  # 不是竞争型
        },
    },
}

# 茉子线 - 共通线选择导向茉子好感度≥2 + c4选"挖野菜"
MAKO_ROUTE = {
    "route_name": "常陆茉子线",
    "route_id": "mako",
    "entry_conditions": [
        "c2 选择'不好说'",
        "c4 选择'挖野菜'",
    ],
    "description": "茉子是芳乃的护卫，一个表面轻浮随性、实则心思细腻的女忍者。她习惯用玩笑和笑容掩盖自己的真实想法。在这条路线中，你帮助她摘下面具，学会在他人面前展现真实的自己。",
    "key_personality_traits": {
        "social_initiative": "中高——需要看穿伪装、主动靠近",
        "emotional_stability": "中——面对她忽冷忽热的态度",
        "social_stimulation_tolerance": "中——适应她的多面性",
        "planning_preference": -0.2,  # 适应她的随性节奏",
    },
    "character_personality_profile": {
        "茉子": {
            "social_initiative": 0.6,    # 表面活泼
            "emotional_stability": -0.2, # 内心敏感
            "novelty_seeking": 0.4,      # 喜欢恶作剧
            "planning_preference": -0.4, # 不喜欢拘束
            "autonomous_judgment": 0.6,  # 有自己的一套准则
        },
    },
}

# 蕾娜线 - 共通线选择导向蕾娜好感度≥2 + c4a选"既然你都这么说了"
LENA_ROUTE = {
    "route_name": "蕾娜·列支敦瑙尔线",
    "route_id": "lena",
    "entry_conditions": [
        "c3 选择'我觉得很可爱'",
        "c4a 选择'既然你都这么说了'",
    ],
    "description": "蕾娜是来自列支敦瑙尔的留学生，天真烂漫、充满好奇心，但对日本文化有着近乎狂热的热爱。在这条路线中，你帮助她找到在异国他乡的归属感，同时也被她的纯粹和热情所感染。",
    "key_personality_traits": {
        "novelty_seeking": "偏高——被她的异文化热情所感染",
        "social_initiative": "中高——需要主动跨越文化隔阂",
        "competition_cooperation": -0.5,  # 倾向于合作与接纳",
        "risk_tolerance": "中——接受跨国恋情的未知",
    },
    "character_personality_profile": {
        "蕾娜": {
            "social_initiative": 0.8,    # 非常外向
            "novelty_seeking": 0.9,      # 极致的新奇寻求
            "emotional_stability": 0.5,  # 乐观开朗
            "abstraction_tendency": -0.5,# 更喜欢具体的文化体验
            "competition_cooperation": -0.8,  # 完全合作型
        },
    },
}

# 小春线 - 二周目解锁
KOHARU_ROUTE = {
    "route_name": "鞍马小春线",
    "route_id": "koharu",
    "entry_conditions": [
        "c1 选择'说实话'",
        "c6 选择'相信小春说的话'",
        "6-3章关键选择 → 小春的笑容",
    ],
    "description": "小春是穗织镇神社的弓道少女。她坚强独立，在学校和弓道场上都表现出色。但在这条路线中，你会发现她隐藏在坚强外表下的另一面——关于家族、关于弓道、关于她为自己定下的苛刻标准。",
    "key_personality_traits": {
        "autonomous_judgment": "中高——尊重她独立的个性",
        "social_initiative": "中——需要耐心打破她的防御",
        "emotional_stability": "中高——面对一个不轻易示弱的女孩",
        "execution_drive": "中——与她一起追求目标",
    },
}

# 芦花线 - 二周目解锁
ROKA_ROUTE = {
    "route_name": "马庭芦花线",
    "route_id": "roka",
    "entry_conditions": [
        "c1 选择'说实话'",
        "c6 选择'相信小春说的话'",
        "6-3章关键选择 → 芦花的笑容",
    ],
    "description": "芦花是温泉旅馆的看板娘，也是将臣来到穗织镇后认识的第一个人。她开朗活泼，总是笑嘻嘻地照顾着所有人。但在这条路线中，你会发现她也有自己的烦恼和梦想——关于家族旅馆的未来、关于自己的位置。",
    "key_personality_traits": {
        "social_initiative": "中高——她总是主动的那个，但你需要回应",
        "competition_cooperation": -0.6,  # 强合作取向",
        "emotional_stability": "中——面对旅馆经营的现实压力",
        "planning_preference": "中——共同规划未来",
    },
}


# ============================================================
# 全路线汇总
# ============================================================

ALL_ROUTES = {
    "yoshino": YOSHINO_ROUTE,
    "murasame": MURASAME_ROUTE,
    "mako": MAKO_ROUTE,
    "lena": LENA_ROUTE,
    "koharu": KOHARU_ROUTE,
    "roka": ROKA_ROUTE,
}

ALL_CHOICES = COMMON_CHOICES

# 方便索引
CHOICE_BY_ID = {c.choice_id: c for c in ALL_CHOICES}


def get_choices_for_route(route_id: str) -> list[GameChoiceNode]:
    """返回特定路线中的所有相关选择点"""
    result = list(COMMON_CHOICES)
    if route_id in ALL_ROUTES:
        route = ALL_ROUTES[route_id]
        # 过滤出该路线特有的选择
        # （目前所有选择都在共通线，个人线内无分支）
        result = [c for c in ALL_CHOICES if route_id in c.route_tags or "共通线" in c.route_tags]
    return result


def get_all_choice_ids() -> list[str]:
    return [c.choice_id for c in ALL_CHOICES]


def get_choice_by_id(choice_id: str) -> GameChoiceNode | None:
    return CHOICE_BY_ID.get(choice_id)
