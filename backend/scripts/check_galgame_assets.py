"""Smoke-test the galgame image generation and serving pipeline.

Run from the repository root:
    python backend/scripts/check_galgame_assets.py --kind background --key smoke-library --prompt "quiet school library, no humans" --force
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.galgame_asset_service import galgame_asset_service  # noqa: E402


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check galgame asset generation, file write, and HTTP serving.")
    parser.add_argument("--kind", choices=["background", "character"], default="background")
    parser.add_argument("--key", default="smoke-library")
    parser.add_argument("--prompt", default="quiet school library at dusk, visual novel CG, no humans")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-generate", action="store_true", help="Only print config/status without generating.")
    args = parser.parse_args()

    print("[galgame-assets] effective config")
    print(
        json.dumps(
            {
                "generation_enabled": settings.galgame_asset_generation_enabled,
                "backend": settings.galgame_asset_backend,
                "base_url": settings.galgame_asset_base_url,
                "api_key": _mask(settings.galgame_asset_api_key),
                "model": settings.galgame_asset_model,
                "response_format": settings.galgame_asset_response_format,
                "public_dir": settings.galgame_asset_public_dir,
                "public_url_prefix": settings.galgame_asset_public_url_prefix,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    status = galgame_asset_service.status()
    print("[galgame-assets] diagnostics")
    for hint in status.get("diagnostics", []):
        print(f"- {hint}")

    if args.no_generate:
        return 0

    print("[galgame-assets] generating or reusing asset")
    asset = galgame_asset_service.generate_image_asset(
        kind=args.kind,
        key=args.key,
        prompt=args.prompt,
        force=args.force,
    )
    payload = asset.model_dump()
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if asset.status != "ready" or not asset.url:
        print("[galgame-assets] ERROR: asset is not ready or URL is empty.")
        return 2

    url = asset.url
    if url.startswith("/api/galgame/assets/"):
        print(f"[galgame-assets] serving through FastAPI TestClient: {url}")
        response = TestClient(app).get(url)
        print(f"[galgame-assets] GET {url} -> {response.status_code}, bytes={len(response.content)}")
        if response.status_code != 200 or not response.content:
            print("[galgame-assets] ERROR: generated file was not served by backend.")
            return 3
    elif url.startswith("/generated/galgame/"):
        print("[galgame-assets] WARNING: asset URL uses old frontend-static prefix.")
        print("[galgame-assets] Set GALGAME_ASSET_PUBLIC_URL_PREFIX=/api/galgame/assets for split frontend/backend deployment.")
    elif url.startswith("http://") or url.startswith("https://"):
        print("[galgame-assets] external URL returned; browser must be able to fetch it directly.")
    else:
        print("[galgame-assets] relative static URL returned; verify it exists under frontend/public in the deployed build.")

    print("[galgame-assets] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
