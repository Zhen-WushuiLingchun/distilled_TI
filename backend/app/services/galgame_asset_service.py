"""Best-effort galgame asset resolution and generation."""

from __future__ import annotations

import base64
from collections import deque
import hashlib
import re
from pathlib import Path
import time
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
            "response_format": settings.galgame_asset_response_format,
            "quality": settings.galgame_asset_quality,
            "watermark": settings.galgame_asset_watermark,
            "size_background": settings.galgame_asset_size_background,
            "size_character": settings.galgame_asset_size_character,
            "sequential_image_generation": settings.galgame_asset_sequential_image_generation,
            "stream": settings.galgame_asset_stream,
            "public_url_prefix": settings.galgame_asset_public_url_prefix,
            "background_count": self._generated_count("background"),
            "character_count": self._generated_count("character"),
            "cache_total_count": self._generated_count(),
            "cache_total_bytes": self._generated_bytes(),
            "cache_max_files": settings.galgame_asset_cache_max_files,
            "cache_max_age_days": settings.galgame_asset_cache_max_age_days,
            "cleanup_enabled": settings.galgame_asset_cleanup_enabled,
            "sdwebui_available": self._probe("sdwebui"),
            "comfyui_available": self._probe("comfyui"),
            "cloud_configured": self._cloud_configured(),
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
        self._generate_image(kind, prompt, output_path, normalized_key)
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

    def generate_senren_character_assets(
        self,
        *,
        personas: dict[str, dict[str, Any]],
        force: bool = False,
    ) -> dict[str, GalgameAssetReference]:
        generated: dict[str, GalgameAssetReference] = {}
        for slug, persona in personas.items():
            display_name = str(persona.get("display_name") or slug)
            generated[slug] = self.generate_image_asset(
                kind="character",
                key=f"senren_{slug}",
                prompt=self._senren_character_prompt(slug, display_name, persona),
                force=force,
            )
        return generated

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
            self._generate_image(kind, prompt, output_path, normalized_key)
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

    def cleanup_generated_assets(
        self,
        *,
        max_files: int | None = None,
        max_age_days: int | None = None,
    ) -> dict[str, int]:
        max_files = settings.galgame_asset_cache_max_files if max_files is None else max_files
        max_age_days = settings.galgame_asset_cache_max_age_days if max_age_days is None else max_age_days
        files = self._generated_files()
        deleted = 0
        now = time.time()

        for path in files:
            if max_age_days > 0 and now - path.stat().st_mtime > max_age_days * 24 * 60 * 60:
                deleted += self._delete_asset_file(path)

        remaining = [path for path in self._generated_files() if path.exists()]
        if max_files > 0 and len(remaining) > max_files:
            remaining.sort(key=lambda item: item.stat().st_mtime)
            for path in remaining[: len(remaining) - max_files]:
                deleted += self._delete_asset_file(path)

        return {
            "deleted_count": deleted,
            "remaining_count": self._generated_count(),
            "remaining_bytes": self._generated_bytes(),
        }

    def _generate_image(self, kind: str, prompt: str, output_path: Path, cache_key: str) -> None:
        backend = settings.galgame_asset_backend.lower()
        if backend == "sdwebui":
            self._generate_sdwebui_image(kind, prompt, output_path, cache_key)
            return
        if backend in {"volcengine", "volcengine_seedream", "seedream"}:
            self._generate_volcengine_seedream_image(kind, prompt, output_path)
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

    def _generate_sdwebui_image(self, kind: str, prompt: str, output_path: Path, cache_key: str) -> None:
        if settings.galgame_asset_backend.lower() != "sdwebui":
            raise ValueError("unsupported_galgame_asset_backend")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._sdwebui_payload(kind, prompt, cache_key)
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
            "size": self._image_size(kind),
            "response_format": settings.galgame_asset_response_format or "b64_json",
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

    def _generate_volcengine_seedream_image(self, kind: str, prompt: str, output_path: Path) -> None:
        if not settings.galgame_asset_api_key.strip():
            raise ValueError("volcengine_seedream_api_key_required")
        if not settings.galgame_asset_model.strip():
            raise ValueError("volcengine_seedream_model_required")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._volcengine_seedream_payload(kind, prompt)
        headers = {
            "Authorization": f"Bearer {settings.galgame_asset_api_key.strip()}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=settings.galgame_asset_timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{settings.galgame_asset_base_url.rstrip('/')}/images/generations",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            self._save_image_api_result(kind, client, data, output_path)

    def _volcengine_seedream_payload(self, kind: str, prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": settings.galgame_asset_model,
            "prompt": self._image_prompt(kind, prompt),
            "n": 1,
            "size": self._image_size(kind),
            "response_format": settings.galgame_asset_response_format or "b64_json",
            "watermark": settings.galgame_asset_watermark,
            "sequential_image_generation": settings.galgame_asset_sequential_image_generation or "disabled",
            "stream": settings.galgame_asset_stream,
        }
        if settings.galgame_asset_quality:
            payload["quality"] = settings.galgame_asset_quality
        return payload

    def _save_image_api_result(
        self,
        kind: str,
        client: httpx.Client,
        data: dict[str, Any],
        output_path: Path,
    ) -> None:
        items = data.get("data") if isinstance(data, dict) else None
        if not items:
            raise ValueError("image_api_empty_data")
        first = items[0]
        if isinstance(first, dict) and first.get("b64_json"):
            self._save_generated_image(kind, output_path, base64.b64decode(str(first["b64_json"]).split(",", 1)[-1]))
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
        if settings.galgame_asset_cleanup_enabled:
            self.cleanup_generated_assets()

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

    def _sdwebui_payload(self, kind: str, prompt: str, cache_key: str = "") -> dict[str, object]:
        seed = self._seed_for(kind, cache_key or prompt)
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
                "seed": seed,
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
            "seed": seed,
            "sampler_name": "DPM++ 2M Karras",
        }

    def _image_size(self, kind: str) -> str:
        if kind == "background":
            return settings.galgame_asset_size_background or "1024x576"
        return settings.galgame_asset_size_character or "576x1024"

    def _cloud_configured(self) -> bool:
        backend = settings.galgame_asset_backend.lower()
        return bool(
            backend in {"volcengine", "volcengine_seedream", "seedream", "openai_images", "openai-image", "image_api"}
            and settings.galgame_asset_base_url.strip()
            and settings.galgame_asset_api_key.strip()
            and settings.galgame_asset_model.strip()
        )

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

    def _senren_character_prompt(self, slug: str, display_name: str, persona: dict[str, Any]) -> str:
        profile = persona.get("profile", {}) if isinstance(persona.get("profile"), dict) else {}
        layer0 = persona.get("layer0", []) if isinstance(persona.get("layer0"), list) else []
        layer2 = persona.get("layer2", {}) if isinstance(persona.get("layer2"), dict) else {}
        layer3 = persona.get("layer3", {}) if isinstance(persona.get("layer3"), dict) else {}
        layer5 = persona.get("layer5", {}) if isinstance(persona.get("layer5"), dict) else {}
        traits = ", ".join(str(item) for item in layer0[:4])
        tone = str(layer2.get("tone") or layer2.get("voice_sample") or "")
        priorities = str(layer3.get("priorities") or "")
        boundaries = ", ".join(str(item) for item in layer5.get("avoids", [])[:3]) if isinstance(layer5.get("avoids"), list) else ""
        role = str(profile.get("role") or "visual novel heroine")
        return (
            "original anime visual novel character sprite, not an existing copyrighted character, "
            "clean lineart, expressive eyes, cohesive game UI asset, transparent background, "
            "front-facing upper body, school-life galgame style, "
            f"character_key={slug}, display_name={display_name}, role={role}, "
            f"personality={traits}, voice_tone={tone}, priorities={priorities}, avoids={boundaries}"
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

    def _generated_count(self, kind: str | None = None) -> int:
        return len(self._generated_files(kind))

    def _generated_bytes(self) -> int:
        return sum(path.stat().st_size for path in self._generated_files())

    def _generated_files(self, kind: str | None = None) -> list[Path]:
        kinds = [kind] if kind else ["background", "character"]
        files: list[Path] = []
        for item in kinds:
            output_dir = self._output_dir(item)
            if output_dir.exists():
                files.extend(output_dir.glob("*.png"))
        return files

    def _delete_asset_file(self, path: Path) -> int:
        try:
            path.unlink()
            return 1
        except FileNotFoundError:
            return 0
        except Exception:
            return 0

    def _seed_for(self, kind: str, cache_key: str) -> int:
        digest = hashlib.sha256(f"{kind}:{cache_key}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 2_147_483_647

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
