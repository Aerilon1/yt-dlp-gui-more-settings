from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HistoryEntry:
    id: int
    url: str
    title: str
    destination_dir: str
    format_label: str
    format_argv_json: str
    subtitle_spec_json: str
    download_section: str
    status: str  # "Finished" | "ERROR"
    started_at: str
    finished_at: str
    error_message: str
