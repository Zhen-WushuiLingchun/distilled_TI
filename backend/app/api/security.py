"""Request-scoped security helpers."""

from __future__ import annotations

import hashlib

from fastapi import HTTPException, Request


def build_owner_key(request: Request) -> str | None:
    host = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "").strip()
    if not host and not user_agent:
        return None
    raw = f"{host}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_local_admin(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=403, detail="admin_local_only")
