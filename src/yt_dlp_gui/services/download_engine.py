"""
Download execution: a QThread per active download running yt-dlp via subprocess (ported
near-verbatim from the pre-rewrite worker.py -- this part was already solid), plus a
DownloadManager dispatcher that gates how many run at once instead of starting every
queued item's subprocess simultaneously.
"""
from __future__ import annotations

import logging
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess as sp
import sys
import tempfile
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore

from ..models.download_item import DownloadItem, DownloadState
from . import paths, win_job as win_job_mod, yt_dlp_args

logger = logging.getLogger(__name__)

_WIN_NO_WINDOW = sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_DASH = "—"


def _write_failure_log(url: str, command: list[str], returncode: int, output: str) -> None:
    """Append a failed download's details to download_failures.log for debugging."""
    try:
        with open(paths.failure_log_path(), "a", encoding="utf-8", errors="replace") as f:
            f.write("\n")
            f.write("=" * 80 + "\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Return code: {returncode}\n")
            f.write("Command:\n  " + " ".join(shlex.quote(str(c)) for c in command) + "\n")
            f.write("yt-dlp output:\n")
            f.write("-" * 40 + "\n")
            f.write(output or "(no output)")
            if output and not output.endswith("\n"):
                f.write("\n")
            f.write("-" * 40 + "\n")
    except Exception:
        logger.exception("Could not write failure log")


def _short_yt_dlp_failure_status(output: str) -> str:
    """One-line status for the queue when yt-dlp exits non-zero (not a substitute for download_failures.log)."""
    if not (output or "").strip():
        return "ERROR"
    low = output.lower()
    if "n challenge solving failed" in low or (
        "javascript runtime" in low and ("no supported" in low or "challenge solver" in low)
    ):
        return "ERROR: YouTube needs a JS runtime (install Deno — see wiki EJS)"
    if "sign in to confirm" in low and "not a bot" in low:
        return "ERROR: YouTube sign-in / bot check (fresh cookies or browser export)"
    if "requested format is not available" in low and "only images are available" in low:
        return "ERROR: No video formats (often JS n-challenge; install Deno or update yt-dlp)"
    if "is not a valid url" in low:
        return "ERROR: Invalid URL (paste a full https:// link)"
    for ln in reversed(output.strip().splitlines()):
        s = ln.strip()
        if s.upper().startswith("ERROR:"):
            msg = s.split(":", 1)[1].strip() if ":" in s else s
            if len(msg) > 80:
                msg = msg[:77] + "..."
            return f"ERROR: {msg}"
    return "ERROR"


# Subtitle-only failures that may appear when --ignore-errors is set (e.g. via global_args);
# these must not flip a successful video download to ERROR.
_SOFT_SUBTITLE_ERROR_MARKERS = (
    "unable to download video subtitles",
    "unable to download subtitles",
    "no subtitles for the requested",
    "there's no subtitles",
    "there are no subtitles",
    "unable to embed subtitle",
)


def _is_soft_subtitle_error_line(line: str) -> bool:
    low = line.lower()
    return any(m in low for m in _SOFT_SUBTITLE_ERROR_MARKERS)


def _hard_failure_despite_zero_exit(output: str) -> bool:
    """
    True when yt-dlp exited 0 (often with --ignore-errors) but the log still shows a
    non-subtitle hard ERROR — i.e. no usable media download should be treated as Finished.
    """
    if not (output or "").strip():
        return False
    for ln in output.splitlines():
        s = ln.strip()
        if not s.upper().startswith("ERROR:"):
            continue
        if _is_soft_subtitle_error_line(s):
            continue
        return True
    return False


def _argv_requests_extract_audio(argv: list[str]) -> bool:
    return "-x" in argv or "--extract-audio" in argv


def _argv_has_compat_no_direct_merge(argv: list[str]) -> bool:
    i = 0
    while i < len(argv):
        if argv[i] == "--compat-options" and i + 1 < len(argv):
            for part in argv[i + 1].split(","):
                if part.strip() == "no-direct-merge":
                    return True
            i += 2
            continue
        i += 1
    return False


def _global_args_tokens(config) -> list[str]:
    g_args = getattr(config, "global_args", "") or ""
    try:
        return shlex.split(g_args)
    except ValueError:
        logger.error("global_args has invalid quoting; fix config.toml (ignored for this download)")
        return []


def _argv_has_absolute_output_path(argv: list[str]) -> bool:
    """
    True if -o/--output uses an absolute filesystem path. yt-dlp then ignores --paths
    for that output; skip temp/home split to avoid surprising behavior.
    """
    i = 0
    while i < len(argv):
        if argv[i] not in ("-o", "--output"):
            i += 1
            continue
        if i + 1 >= len(argv):
            break
        val = argv[i + 1].strip()
        if "%(" in val:
            i += 2
            continue
        candidate = val
        is_win_drive = len(val) >= 2 and val[0].isalpha() and val[1] == ":"
        is_unc = val.startswith("\\\\")
        if not is_win_drive and not is_unc and ":" in val:
            left, _, right = val.partition(":")
            if left and right and left.replace("_", "").isalnum() and left.isascii() and not left[0].isdigit():
                candidate = right
        try:
            if Path(candidate).expanduser().is_absolute():
                return True
        except OSError:
            pass
        i += 2
    return False


def _parse_ytdlp_download_bracket_line(line: str) -> dict[str, str] | None:
    """
    Pull percent / speed / ETA from yt-dlp's normal [download] log lines.
    During --download-sections or fragmented DASH, progress-template lines are often sparse; these lines are not.
    """
    if not line.startswith("[download]"):
        return None
    rest = line[len("[download]"):].lstrip()
    low = rest.lower()
    if any(x in low for x in ("destination:", "sleeping", "has already been downloaded", "resuming download")):
        return None

    m_frag = re.search(r"(?:downloading|merging)\s+(?:video|audio|item|fragment)?\s*(\d+)\s+of\s+(\d+)", low)
    if m_frag and "%" not in rest:
        cur, tot = int(m_frag.group(1)), int(m_frag.group(2))
        if tot > 0:
            pct = max(0, min(99, round(100 * cur / tot)))
            return {"progress": f"{pct}%", "speed": _DASH, "eta": _DASH}

    m_pct = re.search(r"(?P<pct>\d+\.?\d*)%\s+of", rest)
    if not m_pct:
        m_pct = re.search(r"(?P<pct>\d+\.?\d*)%", rest)
    if not m_pct:
        return None
    try:
        float(m_pct.group("pct"))
    except ValueError:
        return None
    out: dict[str, str] = {"progress": f"{round(float(m_pct.group('pct')))}%", "speed": _DASH, "eta": _DASH}
    m_at = re.search(r"\bat\s+(\S+?)\s+ETA\s+(\S+)", rest, re.I)
    if m_at:
        out["speed"] = m_at.group(1).rstrip(",")
        out["eta"] = m_at.group(2)
    else:
        m_in = re.search(r"in\s+\d+:\d+(?::\d+)?\s+at\s+(\S+)", rest, re.I)
        if m_in:
            out["speed"] = m_in.group(1).rstrip(",")
    return out


class DownloadWorker(QtCore.QThread):
    """Runs yt-dlp for one DownloadItem. Progress/finish are reported by item id, not by widget."""

    finished = QtCore.Signal(int)  # item_id
    progress = QtCore.Signal(int, dict)  # item_id, {field_name: value}

    def __init__(self, item: DownloadItem, config, parent=None):
        super().__init__(parent)
        self.item_id = item.id
        self.url = item.url
        self.destination_dir = item.destination_dir
        self.format_spec = item.format_spec
        self.subtitle_spec = item.subtitle_spec
        self.download_section = (item.download_section or "").strip() or None
        self.config = config
        self._home_path = str(Path(self.destination_dir).resolve())
        g_preview = _global_args_tokens(config)
        self._scratch_dir: str | None = None
        if not _argv_has_absolute_output_path(list(self.format_spec.resolved_argv) + g_preview):
            try:
                self._scratch_dir = tempfile.mkdtemp(prefix="yt-dlp-gui-")
            except OSError as e:
                logger.warning(
                    "Could not create temp directory for yt-dlp intermediates (%s); "
                    ".part files may appear in the save folder.",
                    e,
                )
        self.command = self.build_command()
        self._mutex = QtCore.QMutex()
        self._proc_teardown_mutex = QtCore.QMutex()
        self._stop = False
        self._proc: sp.Popen | None = None
        self._reenc_ui_throttle = 0.0

    def build_command(self) -> list[str]:
        args = [
            yt_dlp_args.yt_dlp_program(),
            "--newline",
            "--no-simulate",
            "--progress",
            "--progress-template",
            "%(progress.status)s__SEP__%(progress._total_bytes_estimate_str)s__SEP__"
            "%(progress._percent_str)s__SEP__%(progress._speed_str)s__SEP__"
            "%(progress._eta_str)s__SEP__%(info.title)s",
        ]
        if self._scratch_dir:
            args += ["-P", f"home:{self._home_path}", "-P", f"temp:{self._scratch_dir}"]
        else:
            args += ["-P", self._home_path]
        args += list(self.format_spec.resolved_argv)
        args += _global_args_tokens(self.config)
        args += yt_dlp_args.cookie_args(self.config)
        if self.download_section:
            # Split DASH + --download-sections used to desync A/V; --compat-options no-direct-merge
            # makes video/audio finish separately then merge. Don't rewrite -f -- breaks section quality.
            if not _argv_requests_extract_audio(args) and not _argv_has_compat_no_direct_merge(args):
                args += ["--compat-options", "no-direct-merge"]
            args += ["--download-sections", self.download_section]
            if bool(getattr(self.config, "precise_section_cuts", False)):
                args += ["--force-keyframes-at-cuts"]
        if self.subtitle_spec.enabled:
            mode = self.subtitle_spec.mode
            lang_list = (
                [c for c in self.subtitle_spec.langs if c] if mode in ("all_tracks", "all") else None
            )
            skip_all_modes = mode in ("all_tracks", "all") and not lang_list
            if not skip_all_modes:
                if "--merge-output-format" not in args:
                    args += ["--merge-output-format", "mkv"]
                # No blanket --ignore-errors: missing langs are skipped via --sub-langs lists;
                # --sleep-subtitles reduces flaky subtitle fetches. Hard postprocess failures
                # must not report Finished (run() also scans exit-0 logs if -i is in global_args).
                args += ["--sleep-subtitles", "1"]
                if mode in ("all_tracks", "all"):
                    sub_langs = ",".join(lang_list)
                    if mode == "all_tracks":
                        args += ["--embed-subs", "--sub-langs", sub_langs]
                    else:
                        args += ["--write-subs", "--sub-langs", sub_langs]
                elif mode == "auto_lang":
                    args += ["--write-auto-subs", "--embed-subs", "--sub-langs", self.subtitle_spec.lang or "en"]
                else:  # "lang"
                    args += ["--embed-subs", "--sub-langs", self.subtitle_spec.lang or "en"]
        if "--js-runtimes" not in args:
            args += yt_dlp_args.yt_dlp_js_runtime_argv()
        args += ["--", self.url]
        return args

    def _kill_process_tree_unlocked(self, p: sp.Popen) -> None:
        pid = p.pid
        if sys.platform == "win32":
            win_job_mod.kill_windows_process_tree(pid)
            try:
                p.wait(timeout=10)
            except sp.TimeoutExpired:
                try:
                    p.kill()
                except OSError:
                    pass
        else:
            try:
                os.killpg(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                try:
                    p.terminate()
                except OSError:
                    pass
            try:
                p.wait(timeout=12)
            except sp.TimeoutExpired:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    try:
                        p.kill()
                    except OSError:
                        pass
                try:
                    p.wait(timeout=8)
                except sp.TimeoutExpired:
                    logger.warning("Download (%s) subprocess did not exit after SIGKILL/kill", self.item_id)

    def _teardown_subprocess(self, p: sp.Popen | None) -> None:
        if p is None:
            return
        with QtCore.QMutexLocker(self._proc_teardown_mutex):
            self._kill_process_tree_unlocked(p)

    def stop(self) -> None:
        proc = None
        with QtCore.QMutexLocker(self._mutex):
            self._stop = True
            proc = self._proc
        self._teardown_subprocess(proc)

    def _emit(self, **fields) -> None:
        self.progress.emit(self.item_id, fields)

    def _emit_cancelled(self) -> None:
        self._emit(
            percent_text="0%",
            status_text="Cancelled",
            speed_text=_DASH,
            eta_text=_DASH,
            state=DownloadState.CANCELLED,
        )

    def _process_output_line(self, line: str, out_chunks: list[str]) -> None:
        """Parse one logical line of merged yt-dlp/ffmpeg stdout and update the item."""
        out_chunks.append(line + "\n")
        if "__SEP__" in line:
            parts = [i.strip() for i in line.split("__SEP__", 5)]
            if len(parts) != 6:
                logger.warning("Download (%s) skipping malformed progress line (%d fields)", self.item_id, len(parts))
                return
            _st, total_bytes, percent, speed, eta, title = parts
            if not speed or speed.lower() in ("unknown", "n/a", "na"):
                speed = _DASH
            if not eta or eta.lower() in ("unknown", "n/a", "na"):
                eta = _DASH
            progress_value = percent
            total_low = (total_bytes or "").strip().lower()
            try:
                pct_num = float((percent or "").replace("%", "").strip())
            except (TypeError, ValueError):
                pct_num = None
            if pct_num is None:
                progress_value = "INDETERMINATE"
            elif pct_num <= 0 and total_low in ("", "n/a", "na", "unknown"):
                progress_value = (percent or "0%") if (speed != _DASH or eta != _DASH) else "INDETERMINATE"
            self._emit(
                title=title,
                size_text=total_bytes,
                percent_text=progress_value,
                speed_text=speed,
                eta_text=eta,
                status_text="Downloading",
                state=DownloadState.DOWNLOADING,
            )
        elif line.startswith("[download]"):
            parsed = _parse_ytdlp_download_bracket_line(line)
            if parsed:
                self._emit(
                    status_text="Downloading",
                    percent_text=parsed["progress"],
                    speed_text=parsed.get("speed", _DASH),
                    eta_text=parsed.get("eta", _DASH),
                    state=DownloadState.DOWNLOADING,
                )
            else:
                self._emit(status_text="Downloading", percent_text="INDETERMINATE", state=DownloadState.DOWNLOADING)
        elif line.startswith("[info]") and "Downloading subtitles:" in line:
            self._emit(status_text="Downloading subtitles", percent_text="INDETERMINATE", speed_text=_DASH, eta_text=_DASH)
        elif line.startswith("[youtube]"):
            self._emit(status_text="Fetching metadata", percent_text="INDETERMINATE", speed_text=_DASH, eta_text=_DASH)
        elif line.startswith("[hlsnative]"):
            self._emit(status_text="Downloading fragments", percent_text="INDETERMINATE")
        elif line.startswith("[ffmpeg]"):
            self._emit(status_text="Re-encoding", percent_text="INDETERMINATE", speed_text=_DASH, eta_text=_DASH)
        elif line.startswith(("[Merger]", "[ExtractAudio]", "[VideoRemuxer]", "[EmbedSubtitle]")):
            self._emit(status_text="Converting", percent_text="INDETERMINATE", speed_text=_DASH, eta_text=_DASH)
        elif line.startswith("frame=") or line.startswith("size="):
            now = time.monotonic()
            if now - self._reenc_ui_throttle < 0.2:
                return
            self._reenc_ui_throttle = now
            self._emit(status_text="Re-encoding", percent_text="INDETERMINATE", speed_text=_DASH, eta_text=_DASH)

    def _consume_newline_delimited(self, dec_buf: str, out_chunks: list[str]) -> str:
        while "\n" in dec_buf:
            raw_line, _, dec_buf = dec_buf.partition("\n")
            for piece in raw_line.split("\r"):
                s = piece.strip()
                if s:
                    self._process_output_line(s, out_chunks)
        return dec_buf

    def _consume_cr_delimited_tail(self, dec_buf: str, out_chunks: list[str], final: bool) -> str:
        """
        FFmpeg and some tools emit \\r-delimited updates without newlines. Process completed
        CR segments so the UI advances during long re-encodes; keep the last segment as tail
        until more data arrives (or final=True at EOF).
        """
        if "\r" not in dec_buf:
            return dec_buf
        parts = dec_buf.split("\r")
        if final:
            for piece in parts:
                s = piece.strip()
                if s:
                    self._process_output_line(s, out_chunks)
            return ""
        for piece in parts[:-1]:
            s = piece.strip()
            if s:
                self._process_output_line(s, out_chunks)
        return parts[-1]

    def _pump_stdout(self, p: sp.Popen, out_chunks: list[str]) -> bool:
        """
        Read subprocess stdout in chunks so \\r-only FFmpeg progress does not block readline
        forever. Uses a background thread for blocking reads so cancel is checked on a short
        timeout. Returns True if the user requested cancel/stop.
        """
        out_q: queue.Queue[bytes | None] = queue.Queue()

        def _reader():
            try:
                while True:
                    b = p.stdout.read(8192)
                    out_q.put(b)
                    if not b:
                        break
            finally:
                out_q.put(None)

        threading.Thread(target=_reader, name=f"yt-dlp-gui-worker-{self.item_id}-stdout", daemon=True).start()

        dec_buf = ""
        while True:
            with QtCore.QMutexLocker(self._mutex):
                stop_requested = self._stop
            if stop_requested:
                self._teardown_subprocess(p)
                logger.info("Download (%s) stopped.", self.item_id)
                self._emit_cancelled()
                return True

            try:
                chunk_b = out_q.get(timeout=0.2)
            except queue.Empty:
                continue

            if chunk_b is None:
                dec_buf = self._consume_newline_delimited(dec_buf, out_chunks)
                self._consume_cr_delimited_tail(dec_buf, out_chunks, final=True)
                return False

            if chunk_b:
                dec_buf += chunk_b.decode("utf-8", errors="replace")
                dec_buf = self._consume_newline_delimited(dec_buf, out_chunks)
                dec_buf = self._consume_cr_delimited_tail(dec_buf, out_chunks, final=False)

    def run(self) -> None:
        max_retries = max(0, int(getattr(self.config, "retry_count", 2) or 0))
        attempt = 0
        last_output = ""
        try:
            while attempt <= max_retries:
                attempt += 1
                if attempt > 1:
                    self._emit(status_text=f"Retrying ({attempt - 1}/{max_retries})")
                    delay = 5 if "Access is denied" in last_output else 2
                    deadline = time.monotonic() + delay
                    while time.monotonic() < deadline:
                        with QtCore.QMutexLocker(self._mutex):
                            if self._stop:
                                logger.info("Download (%s) stopped.", self.item_id)
                                self._emit_cancelled()
                                return
                        time.sleep(0.1)

                logger.info(
                    "Download (%s) attempt %s/%s cmd: %s", self.item_id, attempt, max_retries + 1, self.command
                )
                self._emit(status_text="Processing")

                with QtCore.QMutexLocker(self._mutex):
                    if self._stop:
                        logger.info("Download (%s) stopped.", self.item_id)
                        self._emit_cancelled()
                        return

                if self.download_section and bool(getattr(self.config, "precise_section_cuts", False)):
                    self._emit(status_text="Re-encoding cuts (slow)", percent_text="INDETERMINATE")

                child_env = os.environ.copy()
                child_env.setdefault("PYTHONUNBUFFERED", "1")
                popen_kw: dict = dict(
                    stdout=sp.PIPE, stderr=sp.STDOUT, bufsize=0, creationflags=_WIN_NO_WINDOW, env=child_env
                )
                if sys.platform != "win32":
                    popen_kw["start_new_session"] = True

                win_job = win_job_mod.WinDownloadJob() if win_job_mod.WinDownloadJob else None
                out_chunks: list[str] = []
                p: sp.Popen | None = None
                try:
                    p = sp.Popen(self.command, **popen_kw)
                    if win_job is not None:
                        win_job.assign(p.pid)
                    logger.info("Download (%s) started yt-dlp pid=%s", self.item_id, p.pid)
                    with QtCore.QMutexLocker(self._mutex):
                        self._proc = p
                    try:
                        cancelled = self._pump_stdout(p, out_chunks)
                        if cancelled:
                            return
                    finally:
                        with QtCore.QMutexLocker(self._mutex):
                            self._proc = None
                finally:
                    if win_job is not None:
                        win_job.close()
                    if p is not None:
                        with QtCore.QMutexLocker(self._proc_teardown_mutex):
                            try:
                                if p.stdout:
                                    p.stdout.close()
                            except OSError:
                                pass
                            try:
                                p.wait(timeout=120)
                            except sp.TimeoutExpired:
                                logger.warning(
                                    "Download (%s) subprocess did not exit within 120s; forcing kill", self.item_id
                                )
                                self._kill_process_tree_unlocked(p)

                output = "".join(out_chunks)
                last_output = output
                with QtCore.QMutexLocker(self._mutex):
                    stop_requested = self._stop
                if stop_requested:
                    logger.info("Download (%s) stopped.", self.item_id)
                    self._emit_cancelled()
                    return

                if p is None:
                    logger.error("Download (%s) attempt %s: subprocess did not start", self.item_id, attempt)
                    if attempt > max_retries:
                        break
                    continue

                if p.returncode == 0 and not _hard_failure_despite_zero_exit(output):
                    self._emit(percent_text="100%", status_text="Finished", state=DownloadState.FINISHED)
                    return

                if p.returncode == 0:
                    logger.error(
                        "Download (%s) attempt %s exited 0 but hard ERROR in output:\n%s",
                        self.item_id,
                        attempt,
                        output,
                    )
                else:
                    logger.error(
                        "Download (%s) attempt %s returncode: %s\n%s",
                        self.item_id,
                        attempt,
                        p.returncode,
                        output,
                    )
                _write_failure_log(self.url, self.command, p.returncode, output)
                if attempt > max_retries:
                    break

            self._emit(percent_text="0%", status_text=_short_yt_dlp_failure_status(last_output), state=DownloadState.ERROR)
        except Exception:
            logger.exception("Download (%s) worker crashed", self.item_id)
            try:
                _write_failure_log(self.url, self.command, -1, last_output)
            except Exception:
                pass
            self._emit(percent_text="0%", status_text=_short_yt_dlp_failure_status(last_output), state=DownloadState.ERROR)
        finally:
            scratch = getattr(self, "_scratch_dir", None)
            if scratch:
                try:
                    shutil.rmtree(scratch, ignore_errors=True)
                except OSError as e:
                    logger.warning("Could not remove yt-dlp scratch directory %s: %s", scratch, e)
            self.finished.emit(self.item_id)


class DownloadManager(QtCore.QObject):
    """
    Dispatches queued DownloadItems onto at most `max_concurrent` DownloadWorkers at a
    time, instead of starting every queued item's subprocess simultaneously. Items above
    the limit wait in `pending_ids` and are auto-started as running downloads finish.
    """

    item_added = QtCore.Signal(object)  # DownloadItem
    item_updated = QtCore.Signal(int, dict)  # item_id, fields
    item_removed = QtCore.Signal(int)  # item_id
    item_finished = QtCore.Signal(object)  # DownloadItem, for history recording

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.max_concurrent = max(1, int(getattr(config, "max_concurrent_downloads", 3) or 3))
        self.items: dict[int, DownloadItem] = {}
        self.pending_ids: deque[int] = deque()
        self.active_workers: dict[int, DownloadWorker] = {}

    def set_max_concurrent(self, n: int) -> None:
        self.max_concurrent = max(1, int(n))
        self._dispatch()

    def enqueue(self, item: DownloadItem) -> None:
        item.state = DownloadState.QUEUED
        item.status_text = "Queued"
        self.items[item.id] = item
        self.pending_ids.append(item.id)
        self.item_added.emit(item)
        self._dispatch()

    def _dispatch(self) -> None:
        while len(self.active_workers) < self.max_concurrent and self.pending_ids:
            item_id = self.pending_ids.popleft()
            item = self.items.get(item_id)
            if item is None:
                continue
            self._start(item)

    def _start(self, item: DownloadItem) -> None:
        item.state = DownloadState.DOWNLOADING
        item.status_text = "Processing"
        self.item_updated.emit(item.id, {"state": item.state, "status_text": item.status_text})
        worker = DownloadWorker(item, self.config)
        worker.progress.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(worker.deleteLater)
        self.active_workers[item.id] = worker
        worker.start()

    def _on_worker_progress(self, item_id: int, fields: dict) -> None:
        item = self.items.get(item_id)
        if item is None:
            return
        for key, value in fields.items():
            setattr(item, key, value)
        self.item_updated.emit(item_id, fields)

    def _on_worker_finished(self, item_id: int) -> None:
        self.active_workers.pop(item_id, None)
        item = self.items.get(item_id)
        if item is not None and item.state in (DownloadState.FINISHED, DownloadState.ERROR):
            self.item_finished.emit(item)
        self._dispatch()

    def cancel(self, item_id: int) -> None:
        worker = self.active_workers.get(item_id)
        if worker is not None:
            worker.stop()
            return
        if item_id in self.pending_ids:
            self.pending_ids.remove(item_id)
            item = self.items.get(item_id)
            if item is not None:
                item.state = DownloadState.CANCELLED
                item.status_text = "Cancelled"
                self.item_updated.emit(item_id, {"state": item.state, "status_text": item.status_text})

    def remove(self, item_id: int) -> None:
        self.cancel(item_id)
        self.items.pop(item_id, None)
        self.item_removed.emit(item_id)

    def retry(self, item_id: int) -> None:
        """Re-enqueue unchanged: format/subtitle/duration were already baked onto the item."""
        item = self.items.get(item_id)
        if item is None or item_id in self.active_workers or item_id in self.pending_ids:
            return
        item.retry_count += 1
        item.state = DownloadState.QUEUED
        item.status_text = "Queued"
        item.percent_text = "-"
        item.speed_text = "-"
        item.eta_text = "-"
        self.item_updated.emit(
            item_id,
            {
                "state": item.state,
                "status_text": item.status_text,
                "percent_text": "-",
                "speed_text": "-",
                "eta_text": "-",
            },
        )
        self.pending_ids.append(item_id)
        self._dispatch()

    def shutdown(self, wait_ms: int = 12000) -> None:
        self.pending_ids.clear()
        workers = list(self.active_workers.values())
        for w in workers:
            w.stop()
        for w in workers:
            if not w.wait(wait_ms):
                logger.warning("A download thread did not finish within %sms while closing the app.", wait_ms)
