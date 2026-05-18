"""Story Mode character profile catalog.

This module keeps Web Story character selection independent from the disabled
Senren frontend while still reusing the retained skill/persona files.
"""

from __future__ import annotations

import random

from app.domain.models import GalgameCharacterProfile
from app.domain.senren_skills_loader import get_all_personas_cached, get_character_speech_context


ORIGINAL_PROFILES: list[GalgameCharacterProfile] = [
    GalgameCharacterProfile(
        slug="original_rain_recorder",
        display_name="雨间记录员",
        source="builtin",
        role="旧社团楼的临时记录员",
        impression="说话克制、观察细密，会把玩家的回应变成新的线索。",
        tags=["original", "mystery", "campus", "quiet"],
        persona_prompt=(
            "你是雨间记录员，一个原创视觉小说角色。你擅长记录细节，但不会直接替玩家做判断。"
            "你会用自然台词推进校园悬疑，保持温和、克制、有一点试探。"
        ),
        character_key="original_rain_recorder",
        character_prompt="original visual novel character, quiet campus archivist, raincoat accent, expressive half body sprite, non sexualized",
        style_prompt="校园悬疑、低声对话、细节观察、关系缓慢升温。",
    ),
    GalgameCharacterProfile(
        slug="original_rooftop_mender",
        display_name="天台修理师",
        source="builtin",
        role="总在天台修东西的同级生",
        impression="外表散漫，行动力强；会用玩笑掩盖认真判断。",
        tags=["original", "active", "rooftop", "playful"],
        persona_prompt=(
            "你是天台修理师，一个原创视觉小说角色。你讲话轻松但行动很快，"
            "会把玩家拖进实际行动里，同时尊重玩家的选择。"
        ),
        character_key="original_rooftop_mender",
        character_prompt="original visual novel character, rooftop tinkerer student, tool pouch, warm confident expression, half body sprite, non sexualized",
        style_prompt="轻快、行动导向、带玩笑感，但关键时刻认真。",
    ),
    GalgameCharacterProfile(
        slug="original_library_proxy",
        display_name="旧馆代理人",
        source="builtin",
        role="替旧图书馆保管钥匙的人",
        impression="礼貌、疏离、边界感强；只在玩家持续投入时透露更多。",
        tags=["original", "library", "reserved", "boundary"],
        persona_prompt=(
            "你是旧馆代理人，一个原创视觉小说角色。你礼貌但有距离感，"
            "会根据玩家的追问深度逐步开放信息，不要突然热情或跳戏。"
        ),
        character_key="original_library_proxy",
        character_prompt="original visual novel character, old library key keeper, calm reserved gaze, cardigan, half body sprite, non sexualized",
        style_prompt="安静、边界清晰、慢热、偏文学化的校园剧情。",
    ),
]


def _skill_profile(slug: str, persona: dict[str, object]) -> GalgameCharacterProfile:
    display_name = str(persona.get("display_name") or slug)
    profile = persona.get("profile") if isinstance(persona.get("profile"), dict) else {}
    role = str(profile.get("role") or persona.get("description") or "")
    tags_obj = persona.get("tags") if isinstance(persona.get("tags"), dict) else {}
    tags = tags_obj.get("personality") if isinstance(tags_obj.get("personality"), list) else []
    persona_prompt = get_character_speech_context(slug) or (
        f"你是{display_name}。保持稳定人设、稳定边界和自然视觉小说台词。"
    )
    impression = str(persona.get("impression") or "")
    return GalgameCharacterProfile(
        slug=slug,
        display_name=display_name,
        source="skill",
        role=role,
        impression=impression,
        tags=[str(tag) for tag in tags][:10],
        persona_prompt=persona_prompt,
        character_key=f"skill_{slug}",
        character_prompt=(
            f"{display_name}, {role}, original visual novel inspired half body sprite, "
            "consistent character design, expressive face, non sexualized"
        ),
        style_prompt=(
            f"使用留存 skill persona 约束角色语气、优先级、边界和行动方式。角色印象：{impression}"
        ),
    )


def list_story_character_profiles() -> list[GalgameCharacterProfile]:
    profiles = [
        _skill_profile(slug, persona)
        for slug, persona in sorted(get_all_personas_cached().items())
    ]
    return profiles + ORIGINAL_PROFILES


def resolve_story_character_profile(
    mode: str | None = None,
    slug: str | None = None,
) -> GalgameCharacterProfile:
    mode = (mode or "random_skill").strip()
    profiles = list_story_character_profiles()
    by_slug = {profile.slug: profile for profile in profiles}
    skill_profiles = [profile for profile in profiles if profile.source == "skill"]

    if mode == "skill" and slug and slug in by_slug:
        return by_slug[slug]
    if mode == "free":
        return random.choice(ORIGINAL_PROFILES)
    if mode == "random_skill" and skill_profiles:
        return random.choice(skill_profiles)
    if slug and slug in by_slug:
        return by_slug[slug]
    if skill_profiles:
        return random.choice(skill_profiles)
    return ORIGINAL_PROFILES[0]
