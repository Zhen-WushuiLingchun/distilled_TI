from __future__ import annotations

import hashlib
import re
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import unescape
from pathlib import Path
from urllib import error, request


APP_NAME = "DistilledTI Senren Companion"


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def load_env_file() -> None:
    env_path = app_base_dir() / ".env"
    if not env_path.exists():
        return
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"')


load_env_file()
DEFAULT_PORT = int(os.environ.get("SENREN_COMPANION_PORT", "17877"))
VALID_GAME_FILES = (
    "data.xp3",
    "scenario.xp3",
    "script.xp3",
    "scenario.pck",
    "Script.pck",
    "SenrenBanka.exe",
    "千恋＊万花.exe",
    "千恋万花.exe",
)
VALID_GAME_DIRS = ("data", "savedata")
EXE_NAMES = ("SenrenBanka.exe", "千恋＊万花.exe", "千恋万花.exe", "krkr.exe", "kirikiri.exe")
ARCHIVE_SUFFIXES = {".xp3", ".pck"}
SCRIPT_SUFFIXES = {".ks", ".tjs"}
XP3_STORY_NAMES = {"data.xp3", "scenario.xp3", "script.xp3", "scripts.xp3"}
XP3_ASSET_HINTS = ("bg", "fg", "ev", "image", "sound", "voice", "video", "movie", "music", "asset")
SCAN_SKIP_DIRS = {"savedata", "save", "userdata", ".git", "node_modules"}
MAX_LAYOUT_SCAN_FILES = 2000
REMOTE_ERROR_EXCERPT_LIMIT = 900
CLOUDFLARE_CHALLENGE_MARKERS = (
    "just a moment",
    "__cf_chl",
    "challenge-platform",
    "challenges.cloudflare.com",
    "cf-ray",
    "cloudflare",
)


class RemoteRequestError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int | None = None,
        url: str = "",
        detail: str = "",
        hint: str = "",
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.url = url
        self.detail = detail
        self.hint = hint

    def to_payload(self) -> dict:
        payload: dict[str, object] = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.hint:
            payload["hint"] = self.hint
        if self.status_code is not None:
            payload["remote_status"] = self.status_code
        if self.url:
            payload["url"] = self.url
        if self.detail:
            payload["detail_excerpt"] = self.detail[:REMOTE_ERROR_EXCERPT_LIMIT]
        return payload


def _plain_text_excerpt(raw: str) -> str:
    text = raw or ""
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:REMOTE_ERROR_EXCERPT_LIMIT]


def _looks_like_cloudflare_challenge(status_code: int, content_type: str, body: str) -> bool:
    haystack = f"{content_type}\n{body[:6000]}".lower()
    if status_code not in {403, 429, 503}:
        return False
    return any(marker in haystack for marker in CLOUDFLARE_CHALLENGE_MARKERS)


def error_payload(exc: Exception) -> dict:
    if isinstance(exc, RemoteRequestError):
        return exc.to_payload()
    message = str(exc)[:REMOTE_ERROR_EXCERPT_LIMIT] or exc.__class__.__name__
    return {"error": "local_companion_error", "message": message}


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home())
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = root / "DistilledTI" / "senren-companion"
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_PATH = config_dir() / "config.json"
CAPTURE_LOCK = threading.Lock()
CAPTURE_THREAD: threading.Thread | None = None
CAPTURE_STATE: dict[str, object] = {
    "running": False,
    "mode": "clipboard",
    "interval_seconds": 2.0,
    "last_text_hash": "",
    "last_text_excerpt": "",
    "last_error": "",
    "last_sent_at": "",
    "started_at": "",
    "sent_count": 0,
    "probe_count": 0,
}


def default_config() -> dict:
    site_url = os.environ.get("DSTI_SITE_URL", "https://dsti.hydrogenoxide18.com").rstrip("/")
    api_url = os.environ.get("DSTI_API_BASE_URL", f"{site_url}/api").rstrip("/")
    return {
        "site_url": site_url,
        "api_base_url": api_url,
        "game_path": "",
        "user_id": "",
        "user_secret": "",
        "handle": "",
        "active_session_id": "",
        "active_session_secret": "",
    }


def load_config() -> dict:
    config = default_config()
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                config.update({key: str(value) for key, value in saved.items() if value is not None})
        except Exception:
            pass
    return config


def save_config(config: dict) -> dict:
    clean = default_config()
    clean.update({key: str(value) for key, value in config.items() if value is not None})
    CONFIG_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, body: str, content_type: str = "text/html; charset=utf-8") -> None:
    encoded = body.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def game_path_fingerprint(game_path: str) -> str:
    normalized = str(Path(game_path).expanduser().resolve()) if game_path else ""
    return hashlib.sha256(f"senren:{normalized}".encode("utf-8")).hexdigest()[:20]


def _relative_path(root: Path, target: Path) -> str:
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.name


def _archive_role(name: str) -> str:
    lowered = name.lower()
    stem = Path(lowered).stem
    if lowered in XP3_STORY_NAMES or any(marker in stem for marker in ("scenario", "script")):
        return "story_candidate"
    if stem.startswith("patch"):
        return "patch_candidate"
    if any(hint in stem for hint in XP3_ASSET_HINTS):
        return "asset_candidate"
    return "archive"


def _hook_plan_for_layout(primary_story_archive: dict | None, has_xp3: bool) -> dict:
    if primary_story_archive:
        recommended_mode = "text_layer_capture_or_clipboard_bridge"
        reason = f"检测到主剧情包候选 {primary_story_archive['relative_path']}，应优先 hook 文本层或剪贴板桥接，而不是修改 XP3 包。"
    elif has_xp3:
        recommended_mode = "manual_sync_with_archive_inventory"
        reason = "检测到 XP3 包，但未能确定主剧情包；先保留手动同步，并用只读目录摘要辅助定位。"
    else:
        recommended_mode = "manual_sync"
        reason = "未检测到 Kirikiri XP3 布局；当前只能使用手动选择同步。"
    return {
        "recommended_mode": recommended_mode,
        "reason": reason,
        "safe_entrypoints": [
            "read_only_archive_inventory",
            "text_layer_capture_or_clipboard_bridge",
            "ocr_fallback",
            "manual_choice_sync",
        ],
        "do_not": [
            "不要直接修改、重打包或覆盖 data.xp3",
            "不要把原始游戏剧情包或素材上传到服务器",
            "不要注入未审计 DLL 或修改游戏进程内存",
            "不要把正版资源复制进 git 仓库",
        ],
        "next_steps": [
            "先用本 companion 校验真实游戏目录，确认 data.xp3 和 exe 是否存在",
            "如需自动同步，优先实现本机文本层/剪贴板 hook，只向服务器发送当前台词、选择文本和选择结果",
            "若文本层不可用，再做 OCR fallback；服务端仍只保存测量所需的摘要和用户选择",
        ],
    }


def inspect_game_layout(game_path: str) -> dict:
    path = Path(game_path).expanduser()
    base = {
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "engine_family": "unknown",
        "scan_depth": 1,
        "archives": [],
        "script_files": [],
        "executables": [],
        "directories": [],
        "primary_story_archive": None,
        "hook_plan": _hook_plan_for_layout(None, False),
        "risk_notes": [
            "当前只做文件名、大小和相对路径的只读摘要，不解析或上传 data.xp3 内容。",
            "后续自动 hook 应放在用户本机 companion 内，服务器只接收用户授权同步的上下文和选择。",
        ],
    }
    if not path.exists() or not path.is_dir():
        return base

    scan_roots = [path]
    try:
        scan_roots.extend(
            child
            for child in path.iterdir()
            if child.is_dir() and child.name.lower() not in SCAN_SKIP_DIRS
        )
    except OSError:
        pass

    scanned = 0
    archives: list[dict] = []
    script_files: list[str] = []
    executables: list[str] = []
    directories: list[str] = []
    for root in scan_roots:
        try:
            children = list(root.iterdir())
        except OSError:
            continue
        for item in children:
            scanned += 1
            if scanned > MAX_LAYOUT_SCAN_FILES:
                break
            if item.is_dir() and root == path:
                directories.append(item.name)
                continue
            if not item.is_file():
                continue
            suffix = item.suffix.lower()
            rel = _relative_path(path, item)
            if suffix in ARCHIVE_SUFFIXES:
                size_bytes = item.stat().st_size
                archives.append(
                    {
                        "name": item.name,
                        "relative_path": rel,
                        "suffix": suffix,
                        "role": _archive_role(item.name),
                        "size_bytes": size_bytes,
                        "size_mb": round(size_bytes / (1024 * 1024), 2),
                    }
                )
            elif suffix in SCRIPT_SUFFIXES:
                script_files.append(rel)
            elif suffix == ".exe":
                executables.append(rel)
        if scanned > MAX_LAYOUT_SCAN_FILES:
            break

    def story_priority(archive: dict) -> tuple[int, str]:
        name = str(archive.get("name", "")).lower()
        role = str(archive.get("role", ""))
        if name == "data.xp3":
            return (0, name)
        if role == "story_candidate":
            return (1, name)
        if role == "patch_candidate":
            return (2, name)
        return (9, name)

    story_candidates = [
        archive
        for archive in archives
        if archive["suffix"] == ".xp3" and archive["role"] in {"story_candidate", "patch_candidate"}
    ]
    primary_story_archive = sorted(story_candidates, key=story_priority)[0] if story_candidates else None
    has_xp3 = any(archive["suffix"] == ".xp3" for archive in archives)
    has_kirikiri_exe = any(Path(exe).name.lower() in {"krkr.exe", "kirikiri.exe", "senrenbanka.exe"} for exe in executables)

    base.update(
        {
            "engine_family": "kirikiri_xp3" if has_xp3 or has_kirikiri_exe else "unknown",
            "archives": archives,
            "script_files": script_files[:50],
            "executables": executables,
            "directories": directories,
            "primary_story_archive": primary_story_archive,
            "hook_plan": _hook_plan_for_layout(primary_story_archive, has_xp3),
        }
    )
    return base


def validate_game_path(game_path: str) -> dict:
    path = Path(game_path).expanduser()
    layout = inspect_game_layout(game_path)
    if not path.exists() or not path.is_dir():
        return {
            "valid": False,
            "path": str(path),
            "error": "game_path_not_found",
            "hint": f"目录不存在: {game_path}",
            "found_files": [],
            "missing_files": list(VALID_GAME_FILES),
            "found_dirs": [],
            "exe_path": None,
            "fingerprint": "",
            "game_layout": layout,
            "hook_recommendation": layout["hook_plan"],
        }

    found_files: list[str] = []
    missing_files: list[str] = []
    for name in VALID_GAME_FILES:
        if (path / name).exists() or any(
            archive["name"].lower() == name.lower() for archive in layout.get("archives", [])
        ):
            found_files.append(name)
        else:
            missing_files.append(name)

    found_dirs = [name for name in VALID_GAME_DIRS if (path / name).is_dir()]
    exe_path = find_game_exe(path)
    is_valid = bool(found_files or exe_path or layout.get("primary_story_archive"))
    return {
        "valid": is_valid,
        "path": str(path.resolve()),
        "found_files": found_files,
        "missing_files": missing_files,
        "found_dirs": found_dirs,
        "exe_path": str(exe_path) if exe_path else None,
        "fingerprint": game_path_fingerprint(str(path)),
        "game_layout": layout,
        "hook_recommendation": layout["hook_plan"],
        "hint": "目录有效，可启动真实游戏。" if is_valid else "未找到千恋万花关键文件或可执行文件。",
    }


def find_game_exe(path: Path) -> Path | None:
    for name in EXE_NAMES:
        candidate = path / name
        if candidate.is_file():
            return candidate
    for item in path.iterdir():
        if item.is_file() and item.suffix.lower() == ".exe":
            return item
    return None


def launch_game(game_path: str) -> dict:
    validation = validate_game_path(game_path)
    if not validation["valid"] or not validation.get("exe_path"):
        return {"launched": False, "validation": validation, "error": "game_exe_not_found"}
    exe = Path(str(validation["exe_path"]))
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [str(exe)],
                cwd=str(exe.parent),
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [str(exe)],
                cwd=str(exe.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        return {"launched": True, "exe_path": str(exe), "validation": validation}
    except Exception as exc:
        return {"launched": False, "exe_path": str(exe), "validation": validation, "error": str(exc)}


def remote_request(method: str, path: str, payload: dict | None = None, *, include_user: bool = False, include_session: bool = False) -> dict:
    config = load_config()
    api_base_url = config["api_base_url"].rstrip("/")
    url = f"{api_base_url}{path}"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "DistilledTI-Senren-Companion/1.0",
    }
    if include_user:
        headers["X-User-Id"] = config.get("user_id", "")
        headers["X-User-Secret"] = config.get("user_secret", "")
    if include_session:
        headers["X-Session-Secret"] = config.get("active_session_secret", "")
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if method != "GET" else None
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except json.JSONDecodeError as json_exc:
                raise RemoteRequestError(
                    "remote_invalid_json",
                    "远端 API 返回的不是 JSON，companion 无法继续解析。",
                    status_code=getattr(resp, "status", None),
                    url=url,
                    detail=_plain_text_excerpt(raw),
                    hint="检查 API 地址是否正确指向后端 /api，而不是前端页面或 Cloudflare 挑战页。",
                ) from json_exc
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
        detail = _plain_text_excerpt(body)
        if _looks_like_cloudflare_challenge(exc.code, content_type, body):
            raise RemoteRequestError(
                "cloudflare_challenge",
                "远端 API 被 Cloudflare 浏览器挑战页拦截。",
                status_code=exc.code,
                url=url,
                detail=detail,
                hint=(
                    "本机 companion 是 API 客户端，不能执行浏览器 JS challenge。"
                    "请在 Cloudflare 为 /api/health、/api/auth/*、/api/user/*、/api/senren/*"
                    " 或整个 /api/* 配置 WAF Skip/Allow，关闭 Managed Challenge、Bot Fight、"
                    "Browser Integrity Check 对 API 路由的挑战；也可以改用不经过挑战页的 API 子域名。"
                ),
            ) from exc
        raise RemoteRequestError(
            f"remote_http_{exc.code}",
            f"远端 API 返回 HTTP {exc.code}。",
            status_code=exc.code,
            url=url,
            detail=detail,
            hint="检查登录状态、API 地址、服务端日志和反向代理规则。",
        ) from exc
    except RemoteRequestError:
        raise
    except Exception as exc:
        raise RemoteRequestError(
            "remote_request_failed",
            "无法连接远端 API。",
            url=url,
            detail=str(exc),
            hint="检查 API 地址、网络连接、证书、Cloudflare 和后端服务状态。",
        ) from exc


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _capture_status() -> dict:
    with CAPTURE_LOCK:
        return dict(CAPTURE_STATE)


def _set_capture_state(**updates: object) -> dict:
    with CAPTURE_LOCK:
        CAPTURE_STATE.update(updates)
        return dict(CAPTURE_STATE)


def _normalize_captured_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    clean_lines = [line for line in lines if line]
    return "\n".join(clean_lines).strip()


def _capture_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def read_clipboard_text() -> tuple[str, str]:
    """Read the current local clipboard without requiring extra packages."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            text = root.clipboard_get()
        finally:
            root.destroy()
        return _normalize_captured_text(str(text)), ""
    except Exception as tk_exc:
        if sys.platform != "win32":
            return "", f"clipboard_unavailable: {tk_exc}"
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode != 0:
                return "", f"clipboard_unavailable: {tk_exc}; powershell: {result.stderr.strip()}"
            return _normalize_captured_text(result.stdout), ""
        except Exception as ps_exc:
            return "", f"clipboard_unavailable: {tk_exc}; powershell: {ps_exc}"


def _ocr_bbox_from_env() -> tuple[int, int, int, int] | None:
    raw = os.environ.get("SENREN_OCR_REGION", "").strip()
    if not raw:
        return None
    try:
        left, top, width, height = [int(part.strip()) for part in raw.split(",")]
        return (left, top, left + width, top + height)
    except Exception:
        return None


def read_ocr_text() -> tuple[str, str]:
    """OCR the local screen. This is optional and never uploads screenshots."""
    try:
        from PIL import ImageGrab
    except Exception as exc:
        return "", f"ocr_unavailable: Pillow/ImageGrab 未安装或不可用: {exc}"
    try:
        import pytesseract
    except Exception as exc:
        return "", f"ocr_unavailable: pytesseract 未安装: {exc}"

    command = os.environ.get("TESSERACT_CMD", "").strip()
    if command:
        pytesseract.pytesseract.tesseract_cmd = command
    try:
        image = ImageGrab.grab(bbox=_ocr_bbox_from_env())
        language = os.environ.get("SENREN_OCR_LANG", "jpn+chi_sim+eng")
        text = pytesseract.image_to_string(image, lang=language)
        return _normalize_captured_text(text), ""
    except Exception as exc:
        return "", f"ocr_failed: {exc}"


def read_capture_text(mode: str) -> tuple[str, str]:
    if mode == "ocr":
        return read_ocr_text()
    return read_clipboard_text()


def build_capture_event(text: str, mode: str, route_marker: str = "") -> dict:
    normalized = _normalize_captured_text(text)
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    short_lines = [line for line in lines if 1 < len(line) <= 80]
    visible_choices = short_lines[-8:] if len(short_lines) >= 2 and len(normalized) <= 1200 else []
    event_type = "choice_snapshot" if visible_choices else "scene_text"
    return {
        "event_type": event_type,
        "scene_title": route_marker,
        "dialogue_text": normalized[:6000],
        "visible_choices": visible_choices,
        "route_marker": route_marker,
        "source": "ocr" if mode == "ocr" else "clipboard",
        "metadata": {
            "capture_mode": mode,
            "line_count": len(lines),
            "text_hash": _capture_text_hash(normalized),
            "captured_at": _utc_now_iso(),
            "ocr_region": os.environ.get("SENREN_OCR_REGION", ""),
        },
    }


def post_capture_event(text: str, mode: str) -> dict:
    cfg = load_config()
    session_id = cfg.get("active_session_id", "")
    if not session_id:
        raise RuntimeError("no_active_session")
    payload = build_capture_event(text, mode)
    return remote_request(
        "POST",
        f"/senren/companion/{session_id}/event",
        payload,
        include_user=True,
        include_session=True,
    )


def _capture_loop() -> None:
    while True:
        status = _capture_status()
        if not status.get("running"):
            return
        mode = str(status.get("mode") or "clipboard")
        interval = max(float(status.get("interval_seconds") or 2.0), 0.8)
        text, err = read_capture_text(mode)
        if err:
            _set_capture_state(last_error=err)
        elif text:
            text_hash = _capture_text_hash(text)
            if text_hash != status.get("last_text_hash"):
                try:
                    post_capture_event(text, mode)
                    _set_capture_state(
                        last_text_hash=text_hash,
                        last_text_excerpt=text[:240],
                        last_error="",
                        last_sent_at=_utc_now_iso(),
                        sent_count=int(status.get("sent_count") or 0) + 1,
                    )
                except Exception as exc:
                    if str(exc) == "no_active_session":
                        _set_capture_state(last_error=str(exc), last_text_excerpt=text[:240])
                    else:
                        _set_capture_state(
                            last_error=str(exc),
                            last_text_hash=text_hash,
                            last_text_excerpt=text[:240],
                        )
        time.sleep(interval)


def start_capture(payload: dict) -> dict:
    global CAPTURE_THREAD
    mode = str(payload.get("mode") or "clipboard").strip().lower()
    if mode not in {"clipboard", "ocr"}:
        mode = "clipboard"
    try:
        interval = float(payload.get("interval_seconds", 2.0))
    except (TypeError, ValueError):
        interval = 2.0
    interval = min(max(interval, 0.8), 30.0)

    with CAPTURE_LOCK:
        if CAPTURE_STATE.get("running"):
            CAPTURE_STATE.update({"mode": mode, "interval_seconds": interval})
            return dict(CAPTURE_STATE)
        CAPTURE_STATE.update(
            {
                "running": True,
                "mode": mode,
                "interval_seconds": interval,
                "last_error": "",
                "started_at": _utc_now_iso(),
            }
        )
        CAPTURE_THREAD = threading.Thread(target=_capture_loop, daemon=True, name="senren-capture-loop")
        CAPTURE_THREAD.start()
        return dict(CAPTURE_STATE)


def stop_capture() -> dict:
    _set_capture_state(running=False)
    return _capture_status()


def probe_capture(payload: dict) -> dict:
    mode = str(payload.get("mode") or _capture_status().get("mode") or "clipboard").strip().lower()
    if mode not in {"clipboard", "ocr"}:
        mode = "clipboard"
    text, err = read_capture_text(mode)
    _set_capture_state(probe_count=int(_capture_status().get("probe_count") or 0) + 1, last_error=err or "")
    response = {
        "mode": mode,
        "ok": bool(text and not err),
        "error": err,
        "text_excerpt": text[:500],
        "text_length": len(text),
        "event_preview": build_capture_event(text, mode) if text else None,
    }
    if payload.get("send") and text:
        response["sent"] = post_capture_event(text, mode)
    return response


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Senren Local Companion</title>
  <style>
    :root { color-scheme: light; --ink:#222; --muted:#687076; --line:#d8d0c4; --paper:#fffaf0; --bg:#eee7db; --accent:#2f7f68; --warn:#986b21; --danger:#a64040; }
    body { margin:0; font-family: "Microsoft YaHei", "Noto Sans SC", sans-serif; background: radial-gradient(circle at 20% 0%, #fff7df, var(--bg)); color:var(--ink); }
    main { max-width:1180px; margin:0 auto; padding:28px; display:grid; gap:18px; }
    h1 { font-family: Georgia, serif; font-size:42px; margin:0; }
    h2 { margin:0 0 12px; font-size:20px; }
    p { color:var(--muted); line-height:1.7; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:18px; }
    .panel { border:1px solid var(--line); background:rgba(255,250,240,.86); border-radius:18px; padding:18px; box-shadow:0 16px 50px rgba(40,34,24,.08); }
    label { display:block; font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); margin:10px 0 6px; }
    input, select, textarea { width:100%; box-sizing:border-box; border:1px solid var(--line); border-radius:12px; padding:12px; font-size:14px; background:white; color:var(--ink); }
    textarea { min-height:92px; resize:vertical; }
    button { border:0; border-radius:12px; padding:11px 14px; background:var(--accent); color:white; font-weight:700; cursor:pointer; }
    button.secondary { background:#f8f2e7; color:var(--ink); border:1px solid var(--line); }
    button:disabled { opacity:.45; cursor:not-allowed; }
    .row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
    .status { white-space:pre-wrap; border-radius:12px; padding:12px; background:#f7f2e8; color:var(--muted); font-family: ui-monospace, Consolas, monospace; font-size:12px; }
    .choice { display:block; width:100%; margin:8px 0; text-align:left; background:#fff; color:var(--ink); border:1px solid var(--line); }
    .choice.active { border-color:var(--accent); box-shadow: inset 4px 0 0 var(--accent); }
    .pill { border:1px solid var(--line); border-radius:999px; padding:5px 9px; color:var(--muted); font-size:12px; background:#fffaf0; }
    .danger { color:var(--danger); }
    .warn { color:var(--warn); }
  </style>
</head>
<body>
<main>
  <header class="panel">
    <p class="pill">Distilled TI · Senren Local Companion</p>
    <h1>真实游戏选择同步器</h1>
    <p>本程序在你的电脑上运行。它校验并启动真实千恋万花，然后把你在真实游戏里遇到的选择同步到服务器账号。它不会生成伪剧情，也不会读取或修改存档。</p>
  </header>

  <section class="grid">
    <div class="panel">
      <h2>1. 服务器和账号</h2>
      <label>网站地址</label>
      <input id="siteUrl" placeholder="https://dsti.hydrogenoxide18.com" />
      <label>API 地址</label>
      <input id="apiBaseUrl" placeholder="https://dsti.hydrogenoxide18.com/api" />
      <div class="row" style="margin-top:12px">
        <button onclick="saveServerConfig()">保存地址</button>
        <button class="secondary" onclick="openSite()">打开网站</button>
        <button class="secondary" onclick="testRemoteApi()">测试 API</button>
      </div>
      <label>登录邮箱</label>
      <input id="email" placeholder="your@email.com" />
      <label>邮箱验证码</label>
      <input id="code" placeholder="收到验证码后填写" />
      <div class="row" style="margin-top:12px">
        <button onclick="requestLoginCode()">获取验证码</button>
        <button onclick="verifyLoginCode()">验证登录</button>
        <button class="secondary" onclick="loadMe()">测试账号</button>
      </div>
      <div id="authStatus" class="status" style="margin-top:12px"></div>
    </div>

    <div class="panel">
      <h2>2. 本地游戏目录</h2>
      <label>千恋万花安装目录</label>
      <input id="gamePath" placeholder="D:\Games\SenrenBanka" />
      <div class="row" style="margin-top:12px">
        <button onclick="validateGame()">校验目录</button>
        <button onclick="launchGame()">启动真实游戏</button>
      </div>
      <div id="gameStatus" class="status" style="margin-top:12px"></div>
    </div>
  </section>

  <section class="grid">
    <div class="panel">
      <h2>3. 同步真实游戏选择</h2>
      <div class="row">
        <button onclick="startSession()">开始服务器记录</button>
        <button class="secondary" onclick="loadRoadmap()">刷新选择树</button>
        <button class="secondary" onclick="loadSessions()">我的记录</button>
      </div>
      <label>当前章节/选择节点</label>
      <select id="choiceSelect" onchange="renderOptions()"></select>
      <label>真实游戏当前场景标题/位置（可选）</label>
      <input id="sceneTitle" placeholder="例如：共通线第 1 章 · 神社前" />
      <label>真实游戏当前对话/上下文（可选，建议粘贴最近 1-5 句）</label>
      <textarea id="dialogueText" placeholder="把游戏里当前对话或旁白粘贴到这里，服务器只用于本模式测量和报告。"></textarea>
      <label>真实选项文本覆盖（可选；留空则使用选择树文本）</label>
      <input id="choiceTextOverride" placeholder="如果游戏实际文本与面板不同，在这里填写真实选项文本。" />
      <div class="row" style="margin-top:12px">
        <button class="secondary" onclick="syncContextEvent()">只同步当前剧情上下文</button>
      </div>
      <div id="choiceOptions"></div>
      <div id="syncStatus" class="status" style="margin-top:12px"></div>
    </div>

    <div class="panel">
      <h2>4. 报告和网站归档</h2>
      <div class="row">
        <button onclick="generateReport()">生成/刷新报告</button>
        <button class="secondary" onclick="openHistory()">打开网站历史</button>
      </div>
      <div id="reportStatus" class="status" style="margin-top:12px"></div>
      <p class="warn">说明：本机已能只读识别 data.xp3/XP3 布局，并提供手动同步、剪贴板桥接和 OCR 三种入口。服务器不读取、不解析、不保存原始游戏包，只接收授权 companion 上传的当前台词、可见选项和最终选择。</p>
    </div>

    <div class="panel">
      <h2>5. 本机自动捕获</h2>
      <p>自动捕获只在本机运行，并且只把文本摘要通过已登录账号同步到服务器。默认推荐剪贴板桥接；如果游戏不支持复制文本，可安装 Tesseract 后启用 OCR。</p>
      <label>捕获模式</label>
      <select id="captureMode">
        <option value="clipboard">剪贴板桥接（推荐，低延迟）</option>
        <option value="ocr">屏幕 OCR（可选，需要 Tesseract）</option>
      </select>
      <label>轮询间隔（秒）</label>
      <input id="captureInterval" type="number" min="0.8" max="30" step="0.2" value="2" />
      <div class="row" style="margin-top:12px">
        <button onclick="startCapture()">开始自动捕获</button>
        <button class="secondary" onclick="stopCapture()">停止</button>
        <button class="secondary" onclick="probeCapture(false)">探测</button>
        <button class="secondary" onclick="probeCapture(true)">探测并发送</button>
      </div>
      <div id="captureStatus" class="status" style="margin-top:12px"></div>
      <p class="warn">OCR 可用性检查：安装 Tesseract 后可设置环境变量 TESSERACT_CMD；如只想识别窗口局部，可设置 SENREN_OCR_REGION=x,y,w,h。程序不会保存截图。</p>
    </div>
  </section>
</main>
<script>
let roadmap = [];
let challengeId = "";

async function api(path, options = {}) {
  const res = await fetch(path, {
    method: options.method || "GET",
    headers: {"Content-Type": "application/json"},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.message || data.error || data.detail || res.statusText);
    err.payload = data;
    throw err;
  }
  return data;
}

function setText(id, data) {
  document.getElementById(id).textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

function formatError(err) {
  if (err?.payload) return err.payload;
  return {error: "client_error", message: err?.message || String(err)};
}

function showError(id, err) {
  setText(id, formatError(err));
}

async function loadConfig() {
  const cfg = await api("/api/local/config");
  siteUrl.value = cfg.site_url || "";
  apiBaseUrl.value = cfg.api_base_url || "";
  gamePath.value = cfg.game_path || "";
  setText("authStatus", cfg.handle ? `已保存账号：${cfg.handle}` : "尚未登录。");
}

async function saveServerConfig(options = {}) {
  const cfg = await api("/api/local/config", {method:"POST", body:{site_url:siteUrl.value, api_base_url:apiBaseUrl.value, game_path:gamePath.value}});
  if (!options.silent) setText("authStatus", {saved:true, site_url:cfg.site_url, api_base_url:cfg.api_base_url});
  return cfg;
}

async function testRemoteApi() {
  setText("authStatus", "正在测试远端 API...");
  try {
    const data = await api("/api/local/remote-health");
    setText("authStatus", data);
  } catch (err) {
    showError("authStatus", err);
  }
}

async function requestLoginCode() {
  if (!email.value.trim()) {
    setText("authStatus", "请先填写登录邮箱。");
    return;
  }
  setText("authStatus", "正在保存地址并发送验证码...");
  try {
    await saveServerConfig({silent:true});
    const data = await api("/api/local/auth/login", {method:"POST", body:{email:email.value.trim()}});
    challengeId = data.challenge_id || "";
    setText("authStatus", data.dev_code ? {
      status: "本地开发验证码已生成",
      dev_code: data.dev_code,
      challenge_id: challengeId,
    } : {
      status: "验证码已发送，请查看邮箱。",
      email: email.value.trim(),
      challenge_id: challengeId,
    });
  } catch (err) {
    showError("authStatus", err);
  }
}

async function verifyLoginCode() {
  if (!challengeId) {
    setText("authStatus", "请先点击“获取验证码”。");
    return;
  }
  setText("authStatus", "正在验证登录...");
  try {
    const data = await api("/api/local/auth/verify", {method:"POST", body:{email:email.value.trim(), challenge_id:challengeId, code:code.value.trim()}});
    setText("authStatus", data);
  } catch (err) {
    showError("authStatus", err);
  }
}

async function loadMe() {
  setText("authStatus", "正在测试账号...");
  try {
    const data = await api("/api/local/me");
    setText("authStatus", data);
  } catch (err) {
    showError("authStatus", err);
  }
}

async function validateGame() {
  try {
    const data = await api("/api/local/validate-game", {method:"POST", body:{game_path:gamePath.value}});
    setText("gameStatus", data);
  } catch (err) {
    showError("gameStatus", err);
  }
}

async function launchGame() {
  try {
    const data = await api("/api/local/launch-game", {method:"POST", body:{game_path:gamePath.value}});
    setText("gameStatus", data);
  } catch (err) {
    showError("gameStatus", err);
  }
}

async function loadRoadmap() {
  setText("syncStatus", "正在读取服务器选择树...");
  try {
    const data = await api("/api/local/roadmap");
    roadmap = data.nodes || [];
    choiceSelect.innerHTML = roadmap.map((node, idx) => `<option value="${idx}">${node.chapter} · ${node.location} · ${node.choice_id}</option>`).join("");
    renderOptions();
    setText("syncStatus", `已加载 ${roadmap.length} 个真实选择节点。`);
  } catch (err) {
    roadmap = [];
    choiceSelect.innerHTML = "";
    choiceOptions.innerHTML = "";
    showError("syncStatus", err);
  }
}

function renderOptions() {
  const node = roadmap[Number(choiceSelect.value || 0)];
  if (!node) return;
  choiceOptions.innerHTML = `<p>${node.context || ""}</p>` + (node.options || []).map(opt => (
    `<button class="choice" onclick="submitChoice('${node.choice_id}', '${opt.key}')">${opt.text}</button>`
  )).join("");
}

async function startSession() {
  setText("syncStatus", "正在启动服务器记录...");
  try {
    await saveServerConfig({silent:true});
    const validation = await api("/api/local/validate-game", {method:"POST", body:{game_path:gamePath.value}});
    const data = await api("/api/local/sessions/start", {method:"POST", body:{game_info: validation}});
    setText("syncStatus", data);
    try {
      await loadRoadmap();
    } catch (_) {
      // loadRoadmap already renders the error; a started session should remain usable for manual context sync.
    }
  } catch (err) {
    showError("syncStatus", err);
  }
}

async function syncContextEvent() {
  const node = roadmap[Number(choiceSelect.value || 0)];
  const visibleChoices = (node?.options || []).map(opt => opt.text);
  try {
    const data = await api("/api/local/sessions/event", {method:"POST", body:{
      event_type:"scene_text",
      scene_title: sceneTitle.value || node?.location || "",
      dialogue_text: dialogueText.value || node?.context || "",
      visible_choices: visibleChoices,
      route_marker: node?.choice_id || "",
      source:"manual",
    }});
    setText("syncStatus", data);
  } catch (err) {
    showError("syncStatus", err);
  }
}

async function submitChoice(choiceId, optionKey) {
  const node = roadmap[Number(choiceSelect.value || 0)];
  const option = (node?.options || []).find(item => item.key === optionKey);
  try {
    const data = await api("/api/local/sessions/choice", {method:"POST", body:{
      choice_id:choiceId,
      option_key:optionKey,
      choice_text: choiceTextOverride.value || option?.text || "",
      dialogue_text: dialogueText.value || "",
      scene_title: sceneTitle.value || node?.location || "",
    }});
    setText("syncStatus", data);
  } catch (err) {
    showError("syncStatus", err);
  }
}

async function loadSessions() {
  setText("syncStatus", "正在读取我的记录...");
  try {
    const data = await api("/api/local/sessions");
    setText("syncStatus", data);
  } catch (err) {
    showError("syncStatus", err);
  }
}

async function generateReport() {
  setText("reportStatus", "正在生成报告...");
  try {
    const data = await api("/api/local/sessions/report");
    setText("reportStatus", data);
  } catch (err) {
    showError("reportStatus", err);
  }
}

async function loadCaptureStatus() {
  const data = await api("/api/local/capture/status");
  setText("captureStatus", data);
  if (data.mode) captureMode.value = data.mode;
  if (data.interval_seconds) captureInterval.value = data.interval_seconds;
}

async function startCapture() {
  try {
    const data = await api("/api/local/capture/start", {method:"POST", body:{mode:captureMode.value, interval_seconds:Number(captureInterval.value || 2)}});
    setText("captureStatus", data);
  } catch (err) {
    showError("captureStatus", err);
  }
}

async function stopCapture() {
  try {
    const data = await api("/api/local/capture/stop", {method:"POST", body:{}});
    setText("captureStatus", data);
  } catch (err) {
    showError("captureStatus", err);
  }
}

async function probeCapture(send) {
  try {
    const data = await api("/api/local/capture/probe", {method:"POST", body:{mode:captureMode.value, send}});
    setText("captureStatus", data);
  } catch (err) {
    showError("captureStatus", err);
  }
}

function openSite() { window.open(siteUrl.value || "https://dsti.hydrogenoxide18.com", "_blank"); }
function openHistory() { window.open((siteUrl.value || "https://dsti.hydrogenoxide18.com").replace(/\/$/, "") + "/history", "_blank"); }

loadConfig()
  .then(loadCaptureStatus)
  .then(() => setText("syncStatus", "未自动读取选择树；如需同步真实选择，请先确认 API 可用，再点击“刷新选择树”。"))
  .catch(err => showError("syncStatus", err));
setInterval(() => loadCaptureStatus().catch(() => {}), 3000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (APP_NAME, fmt % args))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            if self.path == "/" or self.path.startswith("/?"):
                text_response(self, HTML)
            elif self.path == "/api/local/config":
                json_response(self, load_config())
            elif self.path == "/api/local/remote-health":
                json_response(self, {"ok": True, "remote": remote_request("GET", "/health")})
            elif self.path == "/api/local/me":
                json_response(self, remote_request("GET", "/user/me", include_user=True))
            elif self.path == "/api/local/roadmap":
                json_response(self, remote_request("GET", "/senren/roadmap"))
            elif self.path == "/api/local/sessions":
                json_response(self, remote_request("GET", "/senren/companion/sessions", include_user=True))
            elif self.path == "/api/local/sessions/report":
                cfg = load_config()
                session_id = cfg.get("active_session_id", "")
                if not session_id:
                    raise RuntimeError("no_active_session")
                json_response(self, remote_request("GET", f"/senren/companion/{session_id}/report", include_user=True))
            elif self.path == "/api/local/capture/status":
                json_response(self, _capture_status())
            else:
                json_response(self, {"error": "not_found"}, 404)
        except Exception as exc:
            json_response(self, error_payload(exc), 500)

    def do_POST(self) -> None:
        try:
            payload = read_json(self)
            if self.path == "/api/local/config":
                cfg = load_config()
                cfg.update({key: payload.get(key, cfg.get(key, "")) for key in ("site_url", "api_base_url", "game_path")})
                json_response(self, save_config(cfg))
            elif self.path == "/api/local/auth/login":
                json_response(self, remote_request("POST", "/auth/login", {"email": payload.get("email", "")}))
            elif self.path == "/api/local/auth/verify":
                data = remote_request(
                    "POST",
                    "/auth/login/verify",
                    {
                        "email": payload.get("email", ""),
                        "challenge_id": payload.get("challenge_id", ""),
                        "code": payload.get("code", ""),
                    },
                )
                cfg = load_config()
                cfg.update({"user_id": data.get("user_id", ""), "user_secret": data.get("user_secret", ""), "handle": data.get("handle", "")})
                save_config(cfg)
                json_response(self, {"logged_in": True, "handle": data.get("handle", ""), "user_id": data.get("user_id", "")})
            elif self.path == "/api/local/validate-game":
                game_path = str(payload.get("game_path") or load_config().get("game_path", ""))
                cfg = load_config()
                cfg["game_path"] = game_path
                save_config(cfg)
                json_response(self, validate_game_path(game_path))
            elif self.path == "/api/local/launch-game":
                game_path = str(payload.get("game_path") or load_config().get("game_path", ""))
                json_response(self, launch_game(game_path))
            elif self.path == "/api/local/sessions/start":
                cfg = load_config()
                game_path = cfg.get("game_path", "")
                validation = payload.get("game_info") if isinstance(payload.get("game_info"), dict) else validate_game_path(game_path)
                data = remote_request(
                    "POST",
                    "/senren/companion/start",
                    {
                        "client_id": f"{os.uname().nodename if hasattr(os, 'uname') else os.environ.get('COMPUTERNAME', 'local')}",
                        "game_title": "Senren Banka",
                        "game_path": game_path,
                        "game_path_fingerprint": game_path_fingerprint(game_path),
                        "game_info": validation,
                    },
                    include_user=True,
                )
                cfg.update({"active_session_id": data.get("session_id", ""), "active_session_secret": data.get("session_secret", "")})
                save_config(cfg)
                json_response(self, data)
            elif self.path == "/api/local/sessions/choice":
                cfg = load_config()
                session_id = cfg.get("active_session_id", "")
                if not session_id:
                    raise RuntimeError("no_active_session")
                json_response(
                    self,
                    remote_request(
                        "POST",
                        f"/senren/companion/{session_id}/choice",
                        {
                            "choice_id": payload.get("choice_id", ""),
                            "option_key": payload.get("option_key", ""),
                            "choice_text": payload.get("choice_text", ""),
                            "dialogue_text": payload.get("dialogue_text", ""),
                            "scene_title": payload.get("scene_title", ""),
                        },
                        include_user=True,
                        include_session=True,
                    ),
                )
            elif self.path in ("/api/local/sessions/event", "/api/local/hook/event"):
                cfg = load_config()
                session_id = cfg.get("active_session_id", "")
                if not session_id:
                    raise RuntimeError("no_active_session")
                json_response(
                    self,
                    remote_request(
                        "POST",
                        f"/senren/companion/{session_id}/event",
                        {
                            "event_type": payload.get("event_type", "scene_text"),
                            "scene_title": payload.get("scene_title", ""),
                            "dialogue_text": payload.get("dialogue_text", ""),
                            "visible_choices": payload.get("visible_choices", []),
                            "route_marker": payload.get("route_marker", ""),
                            "source": payload.get("source", "manual"),
                            "metadata": payload.get("metadata", {}),
                        },
                        include_user=True,
                        include_session=True,
                    ),
                )
            elif self.path == "/api/local/capture/start":
                json_response(self, start_capture(payload))
            elif self.path == "/api/local/capture/stop":
                json_response(self, stop_capture())
            elif self.path == "/api/local/capture/probe":
                json_response(self, probe_capture(payload))
            else:
                json_response(self, {"error": "not_found"}, 404)
        except Exception as exc:
            json_response(self, error_payload(exc), 500)


def main() -> None:
    port = DEFAULT_PORT
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"{APP_NAME} listening on {url}")
    print(f"Config: {CONFIG_PATH}")
    if os.environ.get("SENREN_COMPANION_OPEN_BROWSER", "true").strip().lower() not in {"0", "false", "no", "off"}:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    server.serve_forever()


if __name__ == "__main__":
    main()
