"""Run a live OpenAI-compatible chat provider acceptance test.

This script reads provider settings from environment variables or backend/.env.
It does not print API keys.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai_service import AIProviderConfig, ai_service


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _setting(name: str, dotenv: dict[str, str], default: str = "") -> str:
    return os.environ.get(name, dotenv.get(name, default)).strip()


def _has_real_key(value: str) -> bool:
    normalized = value.strip()
    return bool(normalized and normalized not in {"your_deepseek_key", "your_api_key"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Test a live chat provider config.")
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persist the provider config into the local SQLite store after a successful test.",
    )
    args = parser.parse_args()

    dotenv = _read_dotenv(BACKEND_ROOT / ".env")
    provider = _setting("AI_PROVIDER", dotenv, "deepseek")
    base_url = _setting("AI_BASE_URL", dotenv, "https://api.deepseek.com")
    api_key = _setting("AI_API_KEY", dotenv)
    model = _setting("AI_MODEL", dotenv, "deepseek-v4-pro")

    print(f"provider: {provider}")
    print(f"base_url: {base_url}")
    print(f"model: {model}")
    print(f"api_key_configured: {_has_real_key(api_key)}")

    if not _has_real_key(api_key):
        print("AI_API_KEY is missing or still uses a placeholder.")
        return 2

    ok, message = ai_service.test_config(
        AIProviderConfig(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
        )
    )
    print(f"ai_test_ok: {ok}")
    print(f"ai_test_message: {message}")
    if not ok:
        return 1

    if args.save:
        ai_service.configure(provider, model, base_url, api_key)
        print("saved_to_local_store: True")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
