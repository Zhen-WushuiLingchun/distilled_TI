"""Check a deployed Distilled TI public API surface.

This script is meant for server-side AI agents and deployment operators. It
does not print secrets. It validates that the public API is reachable, that
protected endpoints are not accidentally open, and that external clients such
as NextChat or the Senren local companion can talk to the server.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


DEFAULT_API_BASE_URL = os.environ.get("DSTI_API_BASE_URL", "http://127.0.0.1:8000/api")
DEFAULT_SITE_URL = os.environ.get("DSTI_SITE_URL", "")
DEFAULT_CONTEXT_API_KEY = os.environ.get("CONTEXT_ANALYSIS_API_KEY", "")
DEFAULT_USER_ID = os.environ.get("DSTI_USER_ID", "")
DEFAULT_USER_SECRET = os.environ.get("DSTI_USER_SECRET", "")


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None = None
    detail: str = ""
    warning: bool = False


def _normalize_api_base_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not url:
        return DEFAULT_API_BASE_URL.rstrip("/")
    if not url.endswith("/api"):
        url = f"{url}/api"
    return url


def _site_root_from_api_base(api_base_url: str, explicit_site_url: str = "") -> str:
    if explicit_site_url.strip():
        return explicit_site_url.strip().rstrip("/")
    if api_base_url.endswith("/api"):
        return api_base_url[: -len("/api")]
    return api_base_url.rstrip("/")


def _request(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, str], str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
    req = request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers.items()), raw, _parse_json(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), raw, _parse_json(raw)
    except Exception as exc:
        return 0, {}, str(exc), None


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw else None
    except json.JSONDecodeError:
        return None


def _add(results: list[CheckResult], name: str, ok: bool, status: int | None, detail: str, *, warning: bool = False) -> None:
    results.append(CheckResult(name=name, ok=ok, status=status, detail=detail, warning=warning))


def _expect_status(results: list[CheckResult], name: str, status: int, expected: set[int], detail: str) -> bool:
    ok = status in expected
    _add(results, name, ok, status, detail if ok else f"{detail}; expected={sorted(expected)}")
    return ok


def _context_payload() -> dict[str, Any]:
    stamp = int(time.time())
    return {
        "application_id": "deployment-smoke",
        "external_user_id": f"deploy-user-{stamp}",
        "conversation_id": f"deploy-thread-{stamp}",
        "consent_basis": "deployment smoke test for external context analysis integration",
        "channel": "deployment_smoke",
        "locale": "zh-CN",
        "persist": False,
        "persist_messages": False,
        "messages": [
            {"role": "assistant", "content": "我可以帮你整理今天的计划。"},
            {"role": "user", "content": "最近有点累，但我只是想先把学习任务排清楚。"},
        ],
    }


def _redact_present(value: str) -> str:
    return "configured" if value.strip() else "missing"


def run_checks(
    *,
    api_base_url: str,
    site_url: str,
    context_api_key: str,
    user_id: str,
    user_secret: str,
    production: bool,
    origin: str,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    api_base_url = _normalize_api_base_url(api_base_url)
    site_root = _site_root_from_api_base(api_base_url, site_url)

    status, _headers, _raw, data = _request("GET", f"{site_root}/health")
    _expect_status(results, "root_health", status, {200}, f"site_root={site_root}")
    if status == 200 and isinstance(data, dict):
        _add(results, "root_health_payload", data.get("status") == "ok", status, f"status={data.get('status')}")

    status, _headers, _raw, data = _request("GET", f"{api_base_url}/health")
    _expect_status(results, "api_health", status, {200}, f"api_base={api_base_url}")
    if status == 200 and isinstance(data, dict):
        _add(results, "api_health_payload", data.get("status") == "ok", status, f"status={data.get('status')}")

    status, headers, _raw, _data = _request(
        "OPTIONS",
        f"{api_base_url}/context/analyze",
        headers={
            "Origin": origin or site_root,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-context-api-key",
        },
    )
    cors_origin = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin", "")
    cors_ok = status in {200, 204} and bool(cors_origin)
    _add(
        results,
        "context_cors_preflight",
        cors_ok,
        status,
        f"allow_origin={cors_origin or 'missing'}",
        warning=not cors_ok,
    )

    status, _headers, _raw, _data = _request("POST", f"{api_base_url}/context/analyze", payload=_context_payload())
    if status == 200:
        _add(
            results,
            "context_requires_api_key",
            not production,
            status,
            "Context API accepted unauthenticated request; set CONTEXT_ANALYSIS_API_KEY for public deployment.",
            warning=not production,
        )
    else:
        _expect_status(results, "context_requires_api_key", status, {401, 403}, "unauthenticated context request is blocked")

    if context_api_key.strip():
        status, _headers, raw, data = _request(
            "POST",
            f"{api_base_url}/context/analyze",
            payload=_context_payload(),
            headers={"X-Context-API-Key": context_api_key},
        )
        ok = status == 200 and isinstance(data, dict) and bool(data.get("analysis_id")) and "risk_level" in data
        _add(
            results,
            "context_authorized_analyze",
            ok,
            status,
            f"key={_redact_present(context_api_key)} risk_level={data.get('risk_level') if isinstance(data, dict) else 'n/a'} raw={raw[:120] if not ok else ''}",
        )
        query = parse.urlencode({"application_id": "deployment-smoke", "min_risk": "medium", "limit": "5"})
        status, _headers, raw, data = _request(
            "GET",
            f"{api_base_url}/context/alerts?{query}",
            headers={"X-Context-API-Key": context_api_key},
        )
        ok = status == 200 and isinstance(data, dict) and isinstance(data.get("items"), list)
        _add(results, "context_alerts_authorized", ok, status, f"items={len(data.get('items', [])) if isinstance(data, dict) else 'n/a'} raw={raw[:120] if not ok else ''}")
    else:
        _add(
            results,
            "context_authorized_analyze",
            not production,
            None,
            "skipped: no --context-api-key",
            warning=not production,
        )

    status, _headers, raw, data = _request("POST", f"{api_base_url}/session/start", payload={"mode": "core"})
    session_ok = status == 200 and isinstance(data, dict) and data.get("session_id") and data.get("session_secret") and data.get("question")
    _add(results, "public_session_start", session_ok, status, f"session_id_present={bool(data.get('session_id')) if isinstance(data, dict) else False} raw={raw[:120] if not session_ok else ''}")
    if session_ok:
        session_id = str(data["session_id"])
        session_secret = str(data["session_secret"])
        status, _headers, _raw, _data = _request("GET", f"{api_base_url}/session/{session_id}/summary")
        _expect_status(results, "public_session_summary_requires_secret", status, {401}, "summary without X-Session-Secret is blocked")
        status, _headers, raw, summary = _request(
            "GET",
            f"{api_base_url}/session/{session_id}/summary",
            headers={"X-Session-Secret": session_secret},
        )
        ok = status == 200 and isinstance(summary, dict) and summary.get("session_id") == session_id
        _add(results, "public_session_summary_authorized", ok, status, f"raw={raw[:120] if not ok else ''}")

    status, _headers, _raw, _data = _request("GET", f"{api_base_url}/senren/companion/sessions?limit=1")
    _expect_status(results, "senren_companion_sessions_requires_user", status, {401}, "companion sessions require user headers")

    if user_id.strip() and user_secret.strip():
        user_headers = {"X-User-Id": user_id, "X-User-Secret": user_secret}
        status, _headers, raw, data = _request(
            "POST",
            f"{api_base_url}/senren/companion/start",
            payload={
                "client_id": "deployment-smoke-companion",
                "game_title": "Senren Banka",
                "game_path": "",
                "game_path_fingerprint": "deployment-smoke",
                "game_info": {
                    "valid": True,
                    "source": "deployment_smoke",
                    "note": "No local game files are uploaded to the server.",
                },
            },
            headers=user_headers,
        )
        companion_ok = status == 200 and isinstance(data, dict) and data.get("session_id") and data.get("session_secret")
        _add(results, "senren_companion_start_authorized", companion_ok, status, f"raw={raw[:120] if not companion_ok else ''}")
        if companion_ok:
            session_id = str(data["session_id"])
            session_secret = str(data["session_secret"])
            status, _headers, raw, event = _request(
                "POST",
                f"{api_base_url}/senren/companion/{session_id}/event",
                payload={
                    "event_type": "choice_snapshot",
                    "scene_title": "deployment smoke scene",
                    "dialogue_text": "A local hook would send current dialogue here.",
                    "visible_choices": ["Choice A", "Choice B"],
                    "route_marker": "deploy_smoke_marker",
                    "source": "hook",
                    "metadata": {"deployment_smoke": True},
                },
                headers={**user_headers, "X-Session-Secret": session_secret},
            )
            ok = status == 200 and isinstance(event, dict) and event.get("stored_events_count", 0) >= 1
            _add(results, "senren_companion_event_authorized", ok, status, f"raw={raw[:120] if not ok else ''}")
    else:
        _add(results, "senren_companion_authorized_flow", not production, None, "skipped: no --user-id/--user-secret", warning=True)

    return results


def print_results(results: list[CheckResult]) -> None:
    for item in results:
        state = "PASS" if item.ok else ("WARN" if item.warning else "FAIL")
        status = "" if item.status is None else f" status={item.status}"
        print(f"[{state}] {item.name}{status} :: {item.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deployed Distilled TI public API openness and integration readiness.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL, help="Public API base URL, e.g. https://example.com/api")
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL, help="Frontend/site root, e.g. https://example.com")
    parser.add_argument("--origin", default="", help="Browser Origin to use for CORS preflight; defaults to site URL")
    parser.add_argument("--context-api-key", default=DEFAULT_CONTEXT_API_KEY, help="Context API key; can also use CONTEXT_ANALYSIS_API_KEY env")
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="Optional DSTI user id for companion authorized smoke")
    parser.add_argument("--user-secret", default=DEFAULT_USER_SECRET, help="Optional DSTI user secret for companion authorized smoke")
    parser.add_argument("--production", action="store_true", help="Fail if public deployment is missing required auth/key checks")
    args = parser.parse_args()

    print(f"api_base_url: {_normalize_api_base_url(args.api_base_url)}")
    print(f"site_url: {_site_root_from_api_base(_normalize_api_base_url(args.api_base_url), args.site_url)}")
    print(f"context_api_key: {_redact_present(args.context_api_key)}")
    print(f"senren_user_credentials: {'configured' if args.user_id and args.user_secret else 'missing'}")
    print(f"production_mode: {args.production}")

    results = run_checks(
        api_base_url=args.api_base_url,
        site_url=args.site_url,
        context_api_key=args.context_api_key,
        user_id=args.user_id,
        user_secret=args.user_secret,
        production=args.production,
        origin=args.origin,
    )
    print_results(results)
    hard_failures = [item for item in results if not item.ok and not item.warning]
    warnings = [item for item in results if not item.ok and item.warning]
    print(f"summary: pass={len(results) - len(hard_failures) - len(warnings)} warn={len(warnings)} fail={len(hard_failures)}")
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
