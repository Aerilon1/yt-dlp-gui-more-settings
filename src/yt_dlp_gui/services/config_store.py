"""User-configurable settings: load/save/seed against config.toml in the user data dir."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import toml

from . import paths

logger = logging.getLogger(__name__)

DEFAULT_PRESETS = {
    "best": "-f bestvideo+bestaudio/best",
    "mkv": "-f bestvideo+bestaudio/best --merge-output-format mkv",
    "mp4": "-f bv*[vcodec^=avc]+ba[ext=m4a]/b",
    "mp3": "--extract-audio --audio-format mp3 --audio-quality 0",
    "wav": "--extract-audio --audio-format wav --audio-quality 0",
}


class ConfigError(Exception):
    pass


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning("Config value %r is not a valid integer; using %s", value, default)
        return default


@dataclass
class AppConfig:
    path: str = ""
    global_args: str = ""
    retry_count: int = 2
    cookies_file: str = ""
    current_preset: int = 0
    use_saved_preset: bool = False
    precise_section_cuts: bool = False
    max_concurrent_downloads: int = 3
    presets: dict = field(default_factory=lambda: dict(DEFAULT_PRESETS))

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        general = data.get("general") or {}
        presets = data.get("presets") or {}
        merged_presets = dict(DEFAULT_PRESETS)
        merged_presets.update(presets)
        return cls(
            path=str(general.get("path", "")),
            global_args=str(general.get("global_args", "")),
            retry_count=_safe_int(general.get("retry_count", 2), 2),
            cookies_file=str(general.get("cookies_file", "")),
            current_preset=_safe_int(general.get("current_preset", 0), 0),
            use_saved_preset=bool(general.get("use_saved_preset", False)),
            precise_section_cuts=bool(general.get("precise_section_cuts", False)),
            max_concurrent_downloads=max(1, _safe_int(general.get("max_concurrent_downloads", 3), 3)),
            presets=merged_presets,
        )

    def to_dict(self) -> dict:
        return {
            "general": {
                "path": self.path,
                "global_args": self.global_args,
                "retry_count": self.retry_count,
                "cookies_file": self.cookies_file,
                "current_preset": self.current_preset,
                "use_saved_preset": self.use_saved_preset,
                "precise_section_cuts": self.precise_section_cuts,
                "max_concurrent_downloads": self.max_concurrent_downloads,
            },
            "presets": self.presets,
        }


def seed_default_config(dest: Path) -> None:
    """Write a clean, no-personal-data config to `dest` (first run only)."""
    src = paths.default_config_resource_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return
    save_config(AppConfig(), dest)


def load_config(cfg_path: Path | None = None) -> AppConfig:
    cfg_path = cfg_path or paths.config_path()
    if not cfg_path.is_file():
        seed_default_config(cfg_path)
    try:
        data = toml.load(cfg_path)
    except toml.TomlDecodeError as e:
        raise ConfigError(f"Config file at {cfg_path} could not be parsed:\n{e}") from e
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, cfg_path: Path | None = None) -> None:
    cfg_path = cfg_path or paths.config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        toml.dump(config.to_dict(), f)
