"""
Persistent record of completed/failed downloads, browsable and searchable across app
restarts. SQLite (stdlib, no new dependency) rather than a flat JSON file: searching by
title/URL/date needs indexed lookups, not a full rewrite of a growing blob on every insert.
Always touched from the GUI thread (DownloadManager.item_finished fires via a queued Qt
signal already delivered on the main thread), so a single connection is safe.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..models.download_item import DownloadItem, DownloadState
from ..models.history_entry import HistoryEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    destination_dir TEXT NOT NULL,
    format_label TEXT NOT NULL,
    format_argv_json TEXT NOT NULL,
    subtitle_spec_json TEXT NOT NULL,
    download_section TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    error_message TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_history_title ON history(title);
CREATE INDEX IF NOT EXISTS idx_history_url ON history(url);
CREATE INDEX IF NOT EXISTS idx_history_started_at ON history(started_at);
"""


class HistoryStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record_finished_item(self, item: DownloadItem) -> None:
        if item.state not in (DownloadState.FINISHED, DownloadState.ERROR):
            return
        status = "Finished" if item.state == DownloadState.FINISHED else "ERROR"
        error_message = "" if status == "Finished" else item.status_text
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO history "
            "(url, title, destination_dir, format_label, format_argv_json, subtitle_spec_json, "
            " download_section, status, started_at, finished_at, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.url,
                item.title or item.url,
                item.destination_dir,
                item.queue_label(),
                json.dumps(item.format_spec.to_dict()),
                json.dumps(item.subtitle_spec.to_dict()),
                item.download_section or "",
                status,
                item.created_at,
                now,
                error_message,
            ),
        )
        self._conn.commit()

    def search(self, query: str = "", limit: int = 500) -> list[HistoryEntry]:
        q = f"%{query.strip()}%" if query.strip() else "%"
        rows = self._conn.execute(
            "SELECT * FROM history WHERE title LIKE ? OR url LIKE ? ORDER BY started_at DESC LIMIT ?",
            (q, q, limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def delete(self, entry_id: int) -> None:
        self._conn.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        self._conn.commit()


def _row_to_entry(row: sqlite3.Row) -> HistoryEntry:
    return HistoryEntry(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        destination_dir=row["destination_dir"],
        format_label=row["format_label"],
        format_argv_json=row["format_argv_json"],
        subtitle_spec_json=row["subtitle_spec_json"],
        download_section=row["download_section"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error_message=row["error_message"],
    )
