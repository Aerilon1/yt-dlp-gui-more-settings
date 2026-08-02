"""
Filesystem locations for the app: bundled resources vs. user-writable data.

User-writable data (config, cookies, history, logs) always lives in an OS user-data
directory, in dev mode and frozen builds alike -- never beside the source/repo. This is
deliberate: the pre-rewrite app only redirected to %APPDATA% when frozen, which is why a
live config.toml and a cookies.txt with real session cookies ended up sitting next to
source during development.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import platformdirs

APP_NAME = "yt-dlp-gui"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _package_root() -> Path:
    """src/yt_dlp_gui directory (dev mode only -- not meaningful when frozen)."""
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """Directory containing the running application (PyInstaller exe dir, or repo root in dev)."""
    if is_frozen():
        return Path(sys.executable).parent
    return _package_root().parent.parent


def resources_dir() -> Path:
    """Bundled read-only resources (icon, default config template)."""
    if is_frozen():
        for candidate in (app_dir() / "_internal" / "resources", app_dir() / "resources"):
            if candidate.is_dir():
                return candidate
        return app_dir() / "resources"
    return _package_root() / "resources"


def user_data_dir() -> Path:
    d = Path(platformdirs.user_data_dir(APP_NAME, appauthor=False, roaming=True))
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = user_data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return user_data_dir() / "config.toml"


def default_config_resource_path() -> Path:
    return resources_dir() / "config.default.toml"


def history_db_path() -> Path:
    return user_data_dir() / "history.sqlite3"


def cookies_path() -> Path:
    return user_data_dir() / "cookies.txt"


def icon_path() -> Path:
    return resources_dir() / "yt-dlp-gui.ico"


def debug_log_path() -> Path:
    return logs_dir() / "debug.log"


def failure_log_path() -> Path:
    return logs_dir() / "download_failures.log"


def legacy_config_candidates() -> list[Path]:
    """Pre-rewrite config.toml locations, for opt-in import only -- never auto-migrated."""
    candidates: list[Path] = []
    if not is_frozen():
        repo_root = _package_root().parent.parent
        candidates.append(repo_root / "config.toml")
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "yt-dlp-gui" / "config.toml")
    seen = set()
    result = []
    for p in candidates:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        if p.is_file():
            result.append(p)
    return result
