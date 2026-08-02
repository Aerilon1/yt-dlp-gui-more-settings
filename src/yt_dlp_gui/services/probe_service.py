"""
Runs `yt-dlp --dump-json` on a background QThread -- used for both subtitle scanning and
format/quality probing (the pre-rewrite app had two ~90%-identical QThread subclasses for
these; this is the single parameterized replacement), and for flat-playlist detection.
"""
from __future__ import annotations

import logging
import subprocess as sp
import sys

from PySide6 import QtCore

from ..models.playlist_entry import PlaylistEntry
from . import win_job as win_job_mod, yt_dlp_args

logger = logging.getLogger(__name__)

_WIN_NO_WINDOW = sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class ProbeThread(QtCore.QThread):
    """Runs yt-dlp --dump-json for one URL and emits (request_id, url, JSON string or None)."""

    result_ready = QtCore.Signal(int, str, object)  # request_id, url, str | None

    def __init__(self, url: str, config, request_id: int, flat_playlist: bool = False, parent=None):
        super().__init__(parent)
        self.url = url.strip()
        self.config = config
        self.request_id = request_id
        self.flat_playlist = flat_playlist
        self._proc: sp.Popen | None = None
        self._proc_mutex = QtCore.QMutex()

    def request_abort(self) -> None:
        with QtCore.QMutexLocker(self._proc_mutex):
            p = self._proc
        if p is None:
            return
        if sys.platform == "win32":
            win_job_mod.kill_windows_process_tree(p.pid)
        else:
            try:
                p.terminate()
            except OSError:
                pass

    def run(self) -> None:
        # --dump-single-json (not --dump-json) so a playlist/channel URL yields one JSON
        # object with an "entries" list, rather than one JSON object per video.
        cmd = [yt_dlp_args.yt_dlp_program(), "--dump-single-json", "--no-download"]
        if self.flat_playlist:
            cmd.append("--flat-playlist")
        cmd += yt_dlp_args.cookie_args(self.config) + ["--", self.url]
        try:
            p = sp.Popen(
                cmd, stdout=sp.PIPE, stderr=sp.PIPE, encoding="utf-8", errors="replace", creationflags=_WIN_NO_WINDOW
            )
            with QtCore.QMutexLocker(self._proc_mutex):
                self._proc = p
            try:
                out, _err = p.communicate(timeout=60)
            except sp.TimeoutExpired:
                logger.warning("Probe timed out for %s", self.url)
                if sys.platform == "win32":
                    win_job_mod.kill_windows_process_tree(p.pid)
                else:
                    p.kill()
                try:
                    out, _err = p.communicate(timeout=15)
                except Exception:
                    out = ""
            finally:
                with QtCore.QMutexLocker(self._proc_mutex):
                    self._proc = None
            if p.returncode == 0 and out:
                self.result_ready.emit(self.request_id, self.url, out)
            else:
                self.result_ready.emit(self.request_id, self.url, None)
        except Exception as e:
            logger.warning("Probe failed: %s", e)
            with QtCore.QMutexLocker(self._proc_mutex):
                self._proc = None
            self.result_ready.emit(self.request_id, self.url, None)


def abort_thread(thread: QtCore.QThread | None, wait_ms: int = 3000) -> None:
    """Abort a probe/helper QThread; ignore if the C++ object was already deleteLater'd."""
    if thread is None:
        return
    try:
        abort = getattr(thread, "request_abort", None)
        if abort:
            abort()
        if thread.isRunning():
            thread.wait(wait_ms)
    except RuntimeError:
        pass


def is_playlist_info(info: dict | None) -> bool:
    return isinstance(info, dict) and isinstance(info.get("entries"), list)


def _format_duration(seconds) -> str:
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def playlist_entries_from_info(info: dict) -> list[PlaylistEntry]:
    entries = info.get("entries") or []
    result: list[PlaylistEntry] = []
    for i, e in enumerate(entries, start=1):
        if not isinstance(e, dict):
            continue
        url = e.get("webpage_url") or e.get("url") or e.get("id") or ""
        if not url:
            continue
        title = e.get("title") or url
        result.append(
            PlaylistEntry(index=i, title=title, url=url, duration_text=_format_duration(e.get("duration")))
        )
    return result
