"""千恋万花角色 Skills 人设加载器

从 skills/ 目录加载 9 个角色的 Layer 0-5 人格定义，
用于 storymode 角色对话生成和前端 persona 卡片展示。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# skills 目录相对于项目根目录
_SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "skills"

# 角色 slug → 展示名 映射
CHARACTER_SLUG_MAP: dict[str, str] = {
    "yoshino": "芳乃",
    "murasame": "丛雨",
    "mako": "茉子",
    "lena": "蕾娜",
    "koharu": "小春",
    "roka": "芦花",
    "masamichi": "将臣",
    "rentarou": "廉太郎",
    "takafumi": "隆文",
}


def _parse_persona_md(content: str) -> dict[str, Any]:
    """解析 persona.md 的 Layer 结构"""
    result: dict[str, Any] = {
        "layer0": [],
        "layer1": {},
        "layer2": {},
        "layer3": {},
        "layer4": {},
        "layer5": {},
    }

    # Layer 0：核心性格（bullet list）
    l0_match = re.search(r"## Layer 0[：:].*?\n\n(.*?)(?=\n---|\n## Layer)", content, re.DOTALL)
    if l0_match:
        result["layer0"] = [
            line.strip("- ").strip()
            for line in l0_match.group(1).strip().split("\n")
            if line.strip().startswith("-")
        ]

    # Layer 1：身份描述
    l1_match = re.search(r"## Layer 1[：:].*?\n\n(.*?)(?=\n---|\n## )", content, re.DOTALL)
    if l1_match:
        l1_text = l1_match.group(1).strip()
        # 提取角色路线描述
        route_match = re.search(r"角色路线[：:](.*?)(?=\n\n|$)", l1_text, re.DOTALL)
        impression_match = re.search(r"有人这样描述你[：:]\s*[「「](.*?)[」」]", l1_text, re.DOTALL)
        result["layer1"] = {
            "full_text": l1_text,
            "route": route_match.group(1).strip() if route_match else "",
            "impression": impression_match.group(1).strip() if impression_match else "",
        }

    # Layer 2：表达风格
    l2_match = re.search(r"## Layer 2[：:].*?\n\n(.*?)(?=\n---|\n## Layer)", content, re.DOTALL)
    if l2_match:
        l2_text = l2_match.group(1).strip()
        result["layer2"] = _parse_layer2(l2_text)

    # Layer 3：决策与判断
    l3_match = re.search(r"## Layer 3[：:].*?\n\n(.*?)(?=\n---|\n## Layer)", content, re.DOTALL)
    if l3_match:
        l3_text = l3_match.group(1).strip()
        result["layer3"] = _parse_layer3(l3_text)

    # Layer 4：人际行为
    l4_match = re.search(r"## Layer 4[：:].*?\n\n(.*?)(?=\n---|\n## Layer)", content, re.DOTALL)
    if l4_match:
        l4_text = l4_match.group(1).strip()
        result["layer4"] = _parse_layer4(l4_text)

    # Layer 5：边界与雷区
    l5_match = re.search(r"## Layer 5[：:].*?\n\n(.*?)(?=\n---|\n## )", content, re.DOTALL)
    if l5_match:
        l5_text = l5_match.group(1).strip()
        result["layer5"] = _parse_layer5(l5_text)

    return result


def _parse_layer2(text: str) -> dict[str, Any]:
    """解析表达风格层"""
    result: dict[str, Any] = {}
    # 标志性台词
    voice_match = re.search(r"[>＞]\s*[「「](.*?)[」」]", text)
    if voice_match:
        result["voice_sample"] = voice_match.group(1).strip()
    # 高频词
    kw_match = re.search(r"高频词[：:]\s*(.*?)$", text, re.MULTILINE)
    if kw_match:
        result["signature_phrases"] = [p.strip() for p in kw_match.group(1).split("、")]
    # 语速
    pace_match = re.search(r"语速[：:]\s*(.*?)$", text, re.MULTILINE)
    if pace_match:
        result["speaking_pace"] = pace_match.group(1).strip()
    # 敬语
    honorifics_match = re.search(r"敬语使用[：:]\s*(.*?)$", text, re.MULTILINE)
    if honorifics_match:
        result["honorifics"] = honorifics_match.group(1).strip()
    # 语气
    tone_match = re.search(r"语气[：:]\s*(.*?)$", text, re.MULTILINE)
    if tone_match:
        result["tone"] = tone_match.group(1).strip()
    # 标志性句式
    pattern_match = re.search(r"标志性句式[：:]\s*(.*?)$", text, re.MULTILINE)
    if pattern_match:
        result["patterns"] = [p.strip() for p in pattern_match.group(1).split(",")]
    # 情感泄密
    tells_match = re.search(r"情感泄密[：:]\s*(.*?)$", text, re.MULTILINE)
    if tells_match:
        result["emotional_tells"] = tells_match.group(1).strip()
    return result


def _parse_layer3(text: str) -> dict[str, Any]:
    """解析决策判断层"""
    result: dict[str, Any] = {}
    for key, pattern in [
        ("priorities", r"优先级[：:]?\s*\n(.+?)(?:\n\n|\n###|\Z)"),
        ("enthusiasm", r"会积极[回应|推进].*?[：:]?\s*\n((?:\s*-\s*.+\n?)+)"),
        ("caution", r"会谨慎[对待|的情况].*?[：:]?\s*\n((?:\s*-\s*.+\n?)+)"),
        ("how_to_say_no", r"如何说[「「]不[」」].*?[：:]?\s*\n?(.+?)(?:\n\n|\n###|\Z)"),
        ("how_to_handle_doubt", r"如何面对质疑.*?[：:]?\s*\n?(.+?)(?:\n\n|\n###|\Z)"),
    ]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            val = match.group(1).strip()
            if key in ("enthusiasm", "caution"):
                val = [line.strip("- ").strip() for line in val.split("\n") if line.strip().startswith("-")]
            result[key] = val
    return result


def _parse_layer4(text: str) -> dict[str, Any]:
    """解析人际行为层"""
    result: dict[str, Any] = {}
    labels_map = [
        ("with_superiors", r"对上级.*?|对长辈.*?"),
        ("with_juniors", r"对下级.*?|对后辈.*?"),
        ("with_peers", r"对平级.*?|对同伴.*?"),
        ("under_pressure", r"压力下"),
    ]
    for key, label_pattern in labels_map:
        # 匹配 "### 对上级/长辈" 或 "对上级/长辈：" 后面的内容
        match = re.search(
            rf"(?:###\s*)?(?:{label_pattern})[：:]*\s*\n+(.+?)(?=\n(?:##\s|\n##|###\s|\*\*|$))",
            text, re.DOTALL,
        )
        if match:
            val = match.group(1).strip()
            if val:
                result[key] = val
    return result


def _parse_layer5(text: str) -> dict[str, Any]:
    """解析边界雷区层"""
    result: dict[str, Any] = {}
    for key, label in [
        ("dislikes", "不喜欢"),
        ("refuses", "会拒绝"),
        ("excited_by", "会兴奋"),
        ("avoids", "会回避"),
    ]:
        match = re.search(rf"(?:\*\*{label}\*\*|{label}).*?\n((?:\s*-\s*.+\n?)+)", text, re.DOTALL)
        if match:
            result[key] = [line.strip("- ").strip() for line in match.group(1).split("\n") if line.strip().startswith("-")]
    return result


def load_character_persona(slug: str) -> dict[str, Any] | None:
    """加载单个角色的完整 persona"""
    persona_path = _SKILLS_ROOT / slug / "persona.md"
    skill_path = _SKILLS_ROOT / slug / "SKILL.md"
    meta_path = _SKILLS_ROOT / slug / "meta.json"

    if not persona_path.exists():
        return None

    persona_content = persona_path.read_text(encoding="utf-8")
    result = _parse_persona_md(persona_content)

    # 补充 meta.json 信息
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        result["meta"] = meta
        result["display_name"] = meta.get("display_name", slug)
        result["profile"] = meta.get("profile", {})
        result["tags"] = meta.get("tags", {})
        result["impression"] = meta.get("impression", "")
        if "personality_traits" in meta:
            result["personality_traits"] = meta["personality_traits"]
    else:
        result["display_name"] = CHARACTER_SLUG_MAP.get(slug, slug)

    # 补充 SKILL.md 的 description
    if skill_path.exists():
        skill_content = skill_path.read_text(encoding="utf-8")
        fm_match = re.search(r"^---\n(.*?)\n---", skill_content, re.DOTALL)
        if fm_match:
            desc_match = re.search(r"description:\s*(.+)$", fm_match.group(1), re.MULTILINE)
            if desc_match:
                result["description"] = desc_match.group(1).strip()

    return result


def load_all_personas() -> dict[str, dict[str, Any]]:
    """加载所有角色 persona"""
    personas = {}
    for slug in CHARACTER_SLUG_MAP:
        persona = load_character_persona(slug)
        if persona:
            personas[slug] = persona
    return personas


def get_character_speech_context(slug: str) -> str:
    """生成角色的对话上下文提示词（用于 AI 生成角色对话）"""
    persona = load_character_persona(slug)
    if not persona:
        return ""

    display_name = persona.get("display_name", slug)
    l0 = persona.get("layer0", [])
    l2 = persona.get("layer2", {})
    l3 = persona.get("layer3", {})
    l5 = persona.get("layer5", {})

    lines = [f"你是{display_name}。"]

    if l0:
        lines.append("核心性格：")
        for rule in l0[:3]:
            lines.append(f"- {rule}")

    if l2:
        if l2.get("tone"):
            lines.append(f"语气：{l2['tone']}")
        if l2.get("patterns"):
            lines.append(f"口头禅：{', '.join(l2['patterns'][:4])}")
        if l2.get("voice_sample"):
            lines.append(f"说话风格参考：「{l2['voice_sample']}」")

    if l3.get("priorities"):
        lines.append(f"优先级：{l3['priorities']}")

    if l5.get("avoids"):
        lines.append(f"回避话题：{', '.join(l5['avoids'][:3])}")

    return "\n".join(lines)


# 缓存
_persona_cache: dict[str, dict[str, Any]] | None = None


def get_all_personas_cached() -> dict[str, dict[str, Any]]:
    """获取缓存的全部 persona"""
    global _persona_cache
    if _persona_cache is None:
        _persona_cache = load_all_personas()
    return _persona_cache


def get_storymode_character_enrichment(scene_characters: list[str]) -> dict[str, Any]:
    """为 storymode 场景提供角色人设富化数据

    输入场景中出现的角色名列表，返回这些角色的对话风格、决策框架等。
    """
    all_personas = get_all_personas_cached()
    enriched = {}

    for char_name in scene_characters:
        # 找到匹配的 slug
        slug = None
        for s, name in CHARACTER_SLUG_MAP.items():
            if name == char_name or char_name in name:
                slug = s
                break
        if slug and slug in all_personas:
            p = all_personas[slug]
            enriched[char_name] = {
                "display_name": p.get("display_name", char_name),
                "layer0": p.get("layer0", []),
                "layer2": {
                    "tone": p.get("layer2", {}).get("tone", ""),
                    "patterns": p.get("layer2", {}).get("patterns", [])[:3],
                    "voice_sample": p.get("layer2", {}).get("voice_sample", ""),
                    "emotional_tells": p.get("layer2", {}).get("emotional_tells", ""),
                    "speaking_pace": p.get("layer2", {}).get("speaking_pace", ""),
                },
                "layer3": {
                    "priorities": p.get("layer3", {}).get("priorities", ""),
                    "how_to_say_no": p.get("layer3", {}).get("how_to_say_no", ""),
                },
                "impression": p.get("impression", ""),
                "profile": p.get("profile", {}),
                "tags": p.get("tags", {}).get("personality", []),
            }

    return enriched
