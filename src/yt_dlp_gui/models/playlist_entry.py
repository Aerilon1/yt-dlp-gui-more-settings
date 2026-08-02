from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaylistEntry:
    """One row from a yt-dlp --flat-playlist probe."""

    index: int
    title: str
    url: str
    duration_text: str = ""
    selected: bool = True
