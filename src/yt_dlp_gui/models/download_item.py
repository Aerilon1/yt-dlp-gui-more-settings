from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .format_spec import FormatSpec
from .subtitle_spec import SubtitleSpec

_id_counter = itertools.count(1)


def next_item_id() -> int:
    return next(_id_counter)


class DownloadState(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class DownloadItem:
    """
    One row in the download queue. All the settings a download needs (format, subtitles,
    duration clip) are baked onto the item itself at creation time -- nothing is looked up
    from window-level "last used" state later, so retrying item A can never be affected by
    scanning or configuring item B in the meantime.
    """

    url: str
    destination_dir: str
    format_spec: FormatSpec
    subtitle_spec: SubtitleSpec = field(default_factory=SubtitleSpec.none)
    download_section: str | None = None
    id: int = field(default_factory=next_item_id)
    state: DownloadState = DownloadState.QUEUED
    status_text: str = "Queued"
    title: str = ""
    size_text: str = "-"
    percent_text: str = "-"
    speed_text: str = "-"
    eta_text: str = "-"
    source: str = "manual"  # "manual" | "playlist"
    retry_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.url

    def queue_label(self) -> str:
        return self.format_spec.label()
