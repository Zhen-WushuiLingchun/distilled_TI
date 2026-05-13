"""Best-effort galgame asset resolution and generation."""

from __future__ import annotations

import base64
from collections import deque
import re
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.domain.models import GalgameAssetReference

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional runtime safety net
    Image = None


class GalgameAssetService:
    _BACKGROUND_FALLBACKS = {
        "council": "/galgame-assets/backgrounds/council_room.svg",
        "library": "/galgame-assets/backgrounds/night_library.svg",
        "rooftop": "/galgame-assets/backgrounds/campus_rooftop.svg",
        "greenhouse": "/galgame-assets/backgrounds/greenhouse.svg",
        "chat": "/galgame-assets/backgrounds/chat_window.svg",
        "clubroom": "/galgame-assets/backgrounds/custom_evening_clubroom.svg",
        "default": "/galgame-assets/backgrounds/campus_courtyard.svg",
    }
    _CHARACTER_FALLBACKS = {
        "librarian": "/galgame-assets/sprites/librarian.svg",
        "transfer": "/galgame-assets/sprites/transfer_student.svg",
        "recorder": "/galgame-assets/sprites/club_recorder.svg",
        "keeper": "/galgame-assets/sprites/club_recorder.svg",
        "custom": "/galgame-assets/sprites/custom_companion.svg",
        "default": "/galgame-assets/sprites/desk_mate.svg",
    }

    def resolve_scene_assets(
        self,
        *,
        background_key: str,
        background_prompt: str,
        character_key: str,
        character_prompt: str,
        mood: str = "",
    ) -> tuple[GalgameAssetReference, GalgameAssetReference, GalgameAssetReference | None]:
        background = self._resolve_image_asset(
            kind="background",
            key=background_key,
            prompt=background_prompt,
            fallback_url=self._fallback_background(background_key),
            enabled=settings.galgame_asset_generate_backgrounds,
        )
        character = self._resolve_image_asset(
            kind="character",
            key=character_key,
            prompt=character_prompt,
            fallback_url=self._fallback_character(character_key),
            enabled=settings.galgame_asset_generate_characters,
        )
        audio = self._resolve_audio_asset(mood)
        return background, character, audio

    def status(self) -> dict[str, object]:
        return {
            "generation_enabled": settings.galgame_asset_generation_enabled,
            "backend": settings.galgame_asset_backend,
            "base_url": settings.galgame_asset_base_url,
            "model": settings.galgame_asset_model,
            "public_url_prefix": settings.galgame_asset_public_url_prefix,
            "background_count": self._generated_count("background"),
            "character_count": self._generated_count("character"),
            "sdwebui_available": self._probe("sdwebui"),
            "comfyui_available": self._probe("comfyui"),
        }

    def generate_image_asset(
        self,
        *,
        kind: str,
        key: str,
        prompt: str,
        force: bool = False,
    ) -> GalgameAssetReference:
        if kind not in {"background", "character"}:
            raise ValueError("invalid_galgame_asset_kind")
        normalized_key = self._slug(key or kind)
        output_path = self._output_dir(kind) / f"{normalized_key}.png"
        if output_path.exists() and not force:
            return GalgameAssetReference(
                kind=kind,  # type: ignore[arg-type]
                key=normalized_key,
                prompt=prompt,
                url=self._public_url(kind, output_path.name),
                source="generated",
                status="ready",
            )
        self._generate_image(kind, prompt, output_path)
        return GalgameAssetReference(
            kind=kind,  # type: ignore[arg-type]
            key=normalized_key,
            prompt=prompt,
            url=self._public_url(kind, output_path.name),
            source="generated",
            status="ready",
        )

    def generate_story_template_assets(
        self,
        *,
        background_key: str,
        background_prompt: str,
        character_key: str,
        character_prompt: str,
        include_character: bool = False,
        force: bool = False,
    ) -> dict[str, GalgameAssetReference]:
        assets = {
            "background": self.generate_image_asset(
                kind="background",
                key=background_key,
                prompt=background_prompt,
                force=force,
            )
        }
        if include_character:
            assets["character"] = self.generate_image_asset(
                kind="character",
                key=character_key,
                prompt=character_prompt,
                force=force,
            )
        return assets

    def _resolve_image_asset(
        self,
        *,
        kind: str,
        key: str,
        prompt: str,
        fallback_url: str,
        enabled: bool,
    ) -> GalgameAssetReference:
        normalized_key = self._slug(key or "default")
        output_path = self._output_dir(kind) / f"{normalized_key}.png"
        if output_path.exists():
            return GalgameAssetReference(
                kind=kind,  # type: ignore[arg-type]
                key=normalized_key,
                prompt=prompt,
                url=self._public_url(kind, output_path.name),
                source="generated",
                status="ready",
            )

        if not settings.galgame_asset_generation_enabled or not enabled:
            return GalgameAssetReference(
                kind=kind,  # type: ignore[arg-type]
                key=normalized_key,
                prompt=prompt,
                url=fallback_url,
                source="fallback",
                status="ready",
            )

        try:
            self._generate_image(kind, prompt, output_path)
            return GalgameAssetReference(
                kind=kind,  # type: ignore[arg-type]
                key=normalized_key,
                prompt=prompt,
                url=self._public_url(kind, output_path.name),
                source="generated",
                status="ready",
            )
        except Exception:
            return GalgameAssetReference(
                kind=kind,  # type: ignore[arg-type]
                key=normalized_key,
                prompt=prompt,
                url=fallback_url,
                source="fallback",
                status="failed",
            )

    def _generate_image(self, kind: str, prompt: str, output_path: Path) -> None:
        backend = settings.galgame_asset_backend.lower()
        if backend == "sdwebui":
            self._generate_sdwebui_image(kind, prompt, output_path)
            return
        if backend in {"openai_images", "openai-image", "image_api"}:
            self._generate_openai_image(kind, prompt, output_path)
            return
        if backend == "comfyui":
            raise ValueError("comfyui_generation_requires_workflow_adapter")
        raise ValueError("unsupported_galgame_asset_backend")

    def _resolve_audio_asset(self, mood: str) -> GalgameAssetReference | None:
        if not settings.galgame_audio_asset_enabled:
            return GalgameAssetReference(
                kind="audio",
                key=self._slug(mood or "ambient"),
                source="none",
                status="disabled",
            )
        return GalgameAssetReference(
            kind="audio",
            key=self._slug(mood or "ambient"),
            url="/galgame-assets/audio/ambient-room.wav",
            source="fallback",
            status="ready",
        )

    def _generate_sdwebui_image(self, kind: str, prompt: str, output_path: Path) -> None:
        if settings.galgame_asset_backend.lower() != "sdwebui":
            raise ValueError("unsupported_galgame_asset_backend")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._sdwebui_payload(kind, prompt)
        headers = {"Content-Type": "application/json"}
        if settings.galgame_asset_api_key:
            headers["Authorization"] = f"Bearer {settings.galgame_asset_api_key}"
        with httpx.Client(timeout=settings.galgame_asset_timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{settings.galgame_asset_base_url.rstrip('/')}/sdapi/v1/txt2img",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        images = data.get("images") if isinstance(data, dict) else None
        if not images:
            raise ValueError("sdwebui_empty_images")
        encoded = str(images[0]).split(",", 1)[-1]
        self._save_generated_image(kind, output_path, base64.b64decode(encoded))

    def _generate_openai_image(self, kind: str, prompt: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        full_prompt = self._image_prompt(kind, prompt)
        headers = {"Content-Type": "application/json"}
        if settings.galgame_asset_api_key:
            headers["Authorization"] = f"Bearer {settings.galgame_asset_api_key}"
        payload: dict[str, Any] = {
            "prompt": full_prompt,
            "n": 1,
            "size": "1536x864" if kind == "background" else "1024x1536",
        }
        if settings.galgame_asset_model:
            payload["model"] = settings.galgame_asset_model
        with httpx.Client(timeout=settings.galgame_asset_timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{settings.galgame_asset_base_url.rstrip('/')}/images/generations",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not items:
                raise ValueError("image_api_empty_data")
            first = items[0]
            if isinstance(first, dict) and first.get("b64_json"):
                self._save_generated_image(kind, output_path, base64.b64decode(str(first["b64_json"])))
                return
            if isinstance(first, dict) and first.get("url"):
                image_response = client.get(str(first["url"]))
                image_response.raise_for_status()
                self._save_generated_image(kind, output_path, image_response.content)
                return
        raise ValueError("image_api_missing_image")

    def _save_generated_image(self, kind: str, output_path: Path, content: bytes) -> None:
        output_path.write_bytes(content)
        self._postprocess_generated_image(kind, output_path)

    def _postprocess_generated_image(self, kind: str, output_path: Path) -> None:
        if kind != "character" or Image is None:
            return
        try:
            with Image.open(output_path) as source:
                image = source.convert("RGBA")
            background_mask = self._connected_background_mask(image)
            pixels = []
            for index, (red, green, blue, alpha) in enumerate(image.getdata()):
                if background_mask[index]:
                    pixels.append((red, green, blue, 0))
                else:
                    pixels.append((red, green, blue, alpha))
            image.putdata(pixels)
            image.save(output_path)
        except Exception:
            return

    def _connected_background_mask(self, image: Any) -> list[bool]:
        width, height = image.size
        corner_colors = self._corner_background_colors(image)
        visited = [False] * (width * height)
        mask = [False] * (width * height)
        queue: deque[tuple[int, int]] = deque()
        seed_cutoff = 72
        fill_cutoff = 96

        def index_for(x: int, y: int) -> int:
            return y * width + x

        def distance_to_corner_colors(x: int, y: int) -> int:
            red, green, blue, _alpha = image.getpixel((x, y))
            return min(
                abs(red - bg_red) + abs(green - bg_green) + abs(blue - bg_blue)
                for bg_red, bg_green, bg_blue in corner_colors
            )

        for x in range(width):
            for y in (0, height - 1):
                if distance_to_corner_colors(x, y) <= seed_cutoff:
                    queue.append((x, y))
        for y in range(height):
            for x in (0, width - 1):
                if distance_to_corner_colors(x, y) <= seed_cutoff:
                    queue.append((x, y))

        while queue:
            x, y = queue.popleft()
            index = index_for(x, y)
            if visited[index]:
                continue
            visited[index] = True
            if distance_to_corner_colors(x, y) > fill_cutoff:
                continue
            mask[index] = True
            if x > 0:
                queue.append((x - 1, y))
            if x < width - 1:
                queue.append((x + 1, y))
            if y > 0:
                queue.append((x, y - 1))
            if y < height - 1:
                queue.append((x, y + 1))
        return mask

    def _corner_background_colors(self, image: Any) -> list[tuple[int, int, int]]:
        width, height = image.size
        sample_size = max(1, min(12, width // 8, height // 8))
        origins = [
            (0, 0),
            (max(0, width - sample_size), 0),
            (0, max(0, height - sample_size)),
            (max(0, width - sample_size), max(0, height - sample_size)),
        ]
        colors = []
        for left, top in origins:
            samples = [
                (red, green, blue)
                for red, green, blue, _alpha in image.crop((left, top, left + sample_size, top + sample_size)).getdata()
            ]
            if samples:
                colors.append(tuple(sum(pixel[index] for pixel in samples) // len(samples) for index in range(3)))
        return colors or [(0, 0, 0)]

    def _corner_background_color(self, image: Any) -> tuple[int, int, int]:
        width, height = image.size
        sample_size = max(1, min(12, width // 8, height // 8))
        samples: list[tuple[int, int, int]] = []
        origins = [
            (0, 0),
            (max(0, width - sample_size), 0),
            (0, max(0, height - sample_size)),
            (max(0, width - sample_size), max(0, height - sample_size)),
        ]
        for left, top in origins:
            for red, green, blue, _alpha in image.crop((left, top, left + sample_size, top + sample_size)).getdata():
                samples.append((red, green, blue))
        if not samples:
            return (0, 0, 0)
        return tuple(sum(pixel[index] for pixel in samples) // len(samples) for index in range(3))

    def _sdwebui_payload(self, kind: str, prompt: str) -> dict[str, object]:
        if kind == "background":
            return {
                "prompt": (
                    self._image_prompt(kind, prompt)
                ),
                "negative_prompt": "text, watermark, logo, blurry, low quality, distorted, people, character, portrait",
                "width": 960,
                "height": 540,
                "steps": 24,
                "cfg_scale": 7,
                "sampler_name": "DPM++ 2M Karras",
            }
        return {
            "prompt": (
                self._image_prompt(kind, prompt)
            ),
            "negative_prompt": "text, watermark, logo, blurry, low quality, extra limbs, nsfw, nude",
            "width": 512,
            "height": 768,
            "steps": 24,
            "cfg_scale": 7,
            "sampler_name": "DPM++ 2M Karras",
        }

    def _image_prompt(self, kind: str, prompt: str) -> str:
        if kind == "background":
            return (
                "masterpiece, high quality visual novel background, anime game CG, cinematic composition, "
                "no humans, no character, no text, "
                f"{prompt}"
            )
        return (
            "masterpiece, high quality visual novel character sprite, upper body, front view, "
            "transparent or simple background, non sexualized, "
            f"{prompt}"
        )

    def _fallback_background(self, key: str) -> str:
        lowered = key.lower()
        for marker, url in self._BACKGROUND_FALLBACKS.items():
            if marker != "default" and marker in lowered:
                return url
        return self._BACKGROUND_FALLBACKS["default"]

    def _fallback_character(self, key: str) -> str:
        lowered = key.lower()
        for marker, url in self._CHARACTER_FALLBACKS.items():
            if marker != "default" and marker in lowered:
                return url
        return self._CHARACTER_FALLBACKS["default"]

    def _output_dir(self, kind: str) -> Path:
        base = Path(settings.galgame_asset_public_dir)
        if not base.is_absolute():
            base = Path(__file__).resolve().parents[3] / base
        return base / kind

    def _public_url(self, kind: str, filename: str) -> str:
        return f"{settings.galgame_asset_public_url_prefix.rstrip('/')}/{kind}/{filename}"

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
        return slug[:72] or "asset"

    def _generated_count(self, kind: str) -> int:
        output_dir = self._output_dir(kind)
        if not output_dir.exists():
            return 0
        return len(list(output_dir.glob("*.png")))

    def _probe(self, backend: str) -> bool:
        try:
            with httpx.Client(timeout=1.5, follow_redirects=False) as client:
                if backend == "sdwebui":
                    response = client.get(f"{settings.galgame_asset_base_url.rstrip('/')}/sdapi/v1/sd-models")
                    return response.status_code < 500
                if backend == "comfyui":
                    response = client.get("http://127.0.0.1:8188/system_stats")
                    return response.status_code < 500
        except Exception:
            return False
        return False


galgame_asset_service = GalgameAssetService()
