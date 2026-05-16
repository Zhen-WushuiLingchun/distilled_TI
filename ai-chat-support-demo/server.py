"""Standalone AI chat demo that calls the Distilled TI context API.

Run this separately from the main product UI. It demonstrates how any chat
assistant can forward authorized context to the backend support-signal API.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str | None = None


class AnalyzeRequest(BaseModel):
    application_id: str = "ai-chat-support-demo"
    external_user_id: str
    conversation_id: str
    messages: list[ChatMessage] = Field(min_length=1)
    consent_basis: str = "demo user terms allow safety support analysis"
    metadata: dict[str, object] = Field(default_factory=dict)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


app = FastAPI(title="AI Chat Support Signal Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/demo/chat")
def chat(payload: ChatRequest) -> dict[str, object]:
    base_url = _env("DEMO_CHAT_BASE_URL")
    api_key = _env("DEMO_CHAT_API_KEY")
    model = payload.model or _env("DEMO_CHAT_MODEL")
    if not base_url or not api_key or not model:
        return {
            "model": "local-fallback",
            "message": {
                "role": "assistant",
                "content": "我在。你可以慢慢说，我会先理解你刚才的处境，再一起把它拆成能处理的一小步。",
            },
        }

    try:
        with httpx.Client(timeout=float(_env("DEMO_CHAT_TIMEOUT_SECONDS", "30")), follow_redirects=False) as client:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是一个普通 AI 助手。自然对话，提供支持，但不要声称自己能诊断。"
                                "遇到明显即时危险时，建议用户联系当地紧急资源或可信任的人。"
                            ),
                        },
                        *[message.model_dump() for message in payload.messages[-20:]],
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = str(data["choices"][0]["message"]["content"]).strip()
            return {"model": model, "message": {"role": "assistant", "content": content}}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"chat_provider_failed:{exc}") from exc


@app.post("/demo/analyze")
def analyze(payload: AnalyzeRequest) -> dict[str, object]:
    api_base = _env("DISTILLED_TI_API_BASE", "http://127.0.0.1:8000/api")
    headers = {"Content-Type": "application/json"}
    api_key = _env("DISTILLED_TI_CONTEXT_API_KEY")
    if api_key:
        headers["X-Context-API-Key"] = api_key
    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            response = client.post(
                f"{api_base.rstrip('/')}/context/analyze",
                headers=headers,
                json={
                    "application_id": payload.application_id,
                    "external_user_id": payload.external_user_id,
                    "conversation_id": payload.conversation_id,
                    "messages": [message.model_dump() for message in payload.messages],
                    "consent_basis": payload.consent_basis,
                    "channel": "ai_chat_demo",
                    "locale": "zh-CN",
                    "metadata": payload.metadata,
                    "persist": True,
                    "persist_messages": False,
                    "include_debug": True,
                },
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"context_analysis_failed:{exc}") from exc
