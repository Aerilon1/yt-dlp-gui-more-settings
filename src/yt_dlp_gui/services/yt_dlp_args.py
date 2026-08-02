"""Pure yt-dlp argv-building helpers: format selectors, cookies, site detection, JS runtime."""
from __future__ import annotations

import logging
import shlex
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import paths

logger = logging.getLogger(__name__)


def yt_dlp_program() -> str:
    """Resolved path to ``yt-dlp`` on PATH, or the bare command name if not found."""
    w = shutil.which("yt-dlp")
    if w:
        return w
    return "yt-dlp.exe" if sys.platform == "win32" else "yt-dlp"


def yt_dlp_js_runtime_argv() -> list[str]:
    """
    Optional argv for YouTube's JS n-challenge (EJS). yt-dlp needs a JS runtime for some
    videos; this is unrelated to cookies. Returns [] if nothing is found.
    """
    candidates = (
        ("deno", ("deno", "deno.exe")),
        ("node", ("node", "node.exe")),
        ("bun", ("bun", "bun.exe")),
    )
    for runtime, names in candidates:
        for name in names:
            w = shutil.which(name)
            if w:
                return ["--js-runtimes", f"{runtime}:{w}"]
    return []


def _url_hostname(url: str) -> str:
    """Hostname for URL detection. Prepends https:// when urlparse would miss the host (scheme-less links)."""
    s = (url or "").strip()
    if not s:
        return ""
    parsed = urlparse(s)
    host = (parsed.hostname or "").lower()
    if host:
        return host
    if "://" in s:
        return ""
    low = s.lower()
    if not (
        low.startswith(("www.", "m.", "music.", "youtu.", "youtube."))
        or "youtube.com" in low
        or "youtu.be" in low
        or "youtube-nocookie.com" in low
    ):
        return ""
    fixed = urlparse("https://" + s.lstrip("/"))
    return (fixed.hostname or "").lower()


def is_youtube_url(url: str) -> bool:
    """True for youtube.com / youtu.be (and nocookie) URLs -- used for YouTube-specific format presets."""
    host = _url_hostname(url)
    if not host:
        return False
    if host in ("youtu.be", "www.youtu.be"):
        return True
    if host == "youtube.com" or host.endswith(".youtube.com"):
        return True
    if host == "youtube-nocookie.com" or host.endswith(".youtube-nocookie.com"):
        return True
    return False


def video_heights_from_info(info: dict | None) -> list[int]:
    """Distinct video heights from yt-dlp --dump-json `formats`, highest first."""
    if not info or not isinstance(info, dict):
        return []
    heights: set[int] = set()
    for f in info.get("formats") or []:
        if not isinstance(f, dict):
            continue
        h = f.get("height")
        if isinstance(h, float) and h == int(h):
            h = int(h)
        if not isinstance(h, int) or h <= 0:
            continue
        vcodec = f.get("vcodec")
        if not vcodec or vcodec == "none":
            continue
        heights.add(h)
    return sorted(heights, reverse=True)


def build_manual_format_argv(
    file_type: str,
    container: str,
    quality_mode: str,
    max_height: int | None,
    url: str,
) -> list[str]:
    """
    Build yt-dlp argv for format selection (manual mode, not named presets).
    quality_mode: "best" or "height_cap" (use max_height when set).
    """
    ft = (file_type or "video").strip().lower()
    cont = (container or "mp4").strip().lower()
    qm = (quality_mode or "best").strip().lower()
    use_height = qm == "height_cap" and bool(max_height) and max_height > 0

    if ft == "audio":
        af = {"mp3": "mp3", "wav": "wav", "m4a": "m4a"}.get(cont, "mp3")
        return ["--extract-audio", "--audio-format", af, "--audio-quality", "0"]

    merge = {"mkv": "mkv", "mp4": "mp4", "webm": "webm"}.get(cont, "mp4")
    height_sel = f"[height<={max_height}]" if use_height else ""

    if cont == "mp4" and url and is_youtube_url(url):
        if use_height:
            fmt = f"bv*{height_sel}[vcodec^=avc]+ba[ext=m4a]/best{height_sel}[ext=mp4]/b"
        else:
            fmt = "bv*[vcodec^=avc]+ba[ext=m4a]/b"
        return ["-f", fmt, "--merge-output-format", merge]

    if use_height:
        fmt = f"bestvideo{height_sel}+bestaudio/best{height_sel}/best"
    else:
        fmt = "bestvideo+bestaudio/best"
    return ["-f", fmt, "--merge-output-format", merge]


def resolve_preset_argv(preset_key: str, url: str, presets: dict) -> list[str]:
    """
    Map a named preset to yt-dlp argv. The "mp4" preset is YouTube-specific (bv*...);
    for other sites fall back to a generic best-merge so behavior matches plain `yt-dlp URL`.
    """
    raw = (presets or {}).get(preset_key)
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parts = shlex.split(raw)
        except ValueError:
            logger.warning("Preset %r has invalid quoting or escapes; fix config.toml", preset_key)
            return []
    else:
        parts = [str(x) for x in raw]
    if preset_key == "mp4" and url and not is_youtube_url(url):
        return shlex.split("-f bestvideo+bestaudio/best --merge-output-format mp4")
    return parts


def cookie_args(config) -> list[str]:
    """Extra argv for yt-dlp: explicit cookies file, else cookies.txt in user_data_dir if present."""
    base = paths.user_data_dir()
    cf = (getattr(config, "cookies_file", "") or "").strip()
    if cf:
        p = Path(cf).expanduser()
        p = p.resolve() if p.is_absolute() else (base / p).resolve()
        if p.is_file():
            return ["--cookies", str(p)]
        logger.debug("Configured cookies file does not exist (skipping --cookies): %s", p)
    auto = paths.cookies_path()
    if auto.is_file():
        return ["--cookies", str(auto)]
    return []


def default_cookies_file_display(config) -> str:
    """Path to show in the cookies file field: config value, else cookies.txt in user_data_dir if present."""
    cf = (getattr(config, "cookies_file", "") or "").strip()
    if cf:
        return cf
    auto = paths.cookies_path()
    if auto.is_file():
        return str(auto.resolve())
    return ""
