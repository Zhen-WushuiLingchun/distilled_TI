"""Offline calibration cases for galgame free-text tendency classification."""

from __future__ import annotations

from app.domain.models import GalgameChoice


CALIBRATION_CHOICES: list[GalgameChoice] = [
    GalgameChoice(
        key="choice-1",
        text="先退后一步，保留距离，等局势更清楚再说",
        option_key="guarded",
        score=-1.0,
        tone="guarded",
    ),
    GalgameChoice(
        key="choice-2",
        text="暂时不表态，继续观察每个人真实在意什么",
        option_key="observe",
        score=0.0,
        tone="ambivalent",
    ),
    GalgameChoice(
        key="choice-3",
        text="主动接下任务，推动大家马上开始行动",
        option_key="direct",
        score=1.0,
        tone="direct",
    ),
]


FREE_TEXT_CALIBRATION_CASES: list[dict[str, str]] = [
    {
        "text": "我先不急着站队，想听完他们各自担心什么。",
        "expected_option_key": "observe",
        "label": "explicit_observe_zh",
    },
    {
        "text": "先等等，我不想现在就被卷进这个决定。",
        "expected_option_key": "guarded",
        "label": "explicit_guarded_zh",
    },
    {
        "text": "我来把任务拆开，今晚就推进第一步。",
        "expected_option_key": "direct",
        "label": "explicit_direct_zh",
    },
    {
        "text": "I would wait, observe the room, and avoid forcing a decision.",
        "expected_option_key": "observe",
        "label": "observe_en",
    },
    {
        "text": "No, I would step back and decline the request for now.",
        "expected_option_key": "guarded",
        "label": "guarded_en",
    },
    {
        "text": "I will offer a plan and push the group to start.",
        "expected_option_key": "direct",
        "label": "direct_en",
    },
    {
        "text": "如果气氛太僵，我会先把话题放慢，不立刻承诺。",
        "expected_option_key": "observe",
        "label": "soft_observe_zh",
    },
    {
        "text": "我不会接这个锅，先把边界讲清楚。",
        "expected_option_key": "guarded",
        "label": "boundary_guarded_zh",
    },
    {
        "text": "既然没人动，我就先开口把安排定下来。",
        "expected_option_key": "direct",
        "label": "initiative_direct_zh",
    },
]


def build_calibration_choices() -> list[GalgameChoice]:
    return [choice.model_copy(deep=True) for choice in CALIBRATION_CHOICES]
