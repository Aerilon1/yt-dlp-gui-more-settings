"""
Startup preflight: ffmpeg/ffprobe/yt-dlp on PATH are hard requirements (block startup if
missing); a JS runtime (deno/node/bun) is a soft requirement for YouTube's n-challenge
(warn only). Replaces the pre-rewrite dep_dl.py gate, which showed a "missing tools"
error dialog but then unconditionally launched the app anyway.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field

from . import yt_dlp_args

REQUIRED_TOOLS = ("ffmpeg", "ffprobe", "yt-dlp")


@dataclass
class DependencyStatus:
    missing_required: list[str] = field(default_factory=list)
    js_runtime_available: bool = True

    @property
    def ok(self) -> bool:
        return not self.missing_required


def check_dependencies() -> DependencyStatus:
    missing = [name for name in REQUIRED_TOOLS if not shutil.which(name)]
    js_ok = bool(yt_dlp_args.yt_dlp_js_runtime_argv())
    return DependencyStatus(missing_required=missing, js_runtime_available=js_ok)
