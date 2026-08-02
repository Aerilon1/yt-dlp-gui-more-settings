"""Runs `yt-dlp -U` via QProcess and turns the result into a short, specific status message."""
from __future__ import annotations

import logging

from PySide6 import QtCore

from . import yt_dlp_args

logger = logging.getLogger(__name__)


def status_message(combined_output: str, exit_code: int, crashed: bool, q_error: str) -> tuple[str, int]:
    """Return (status_bar_text, show_ms) after yt-dlp -U finishes."""
    text = (combined_output or "").strip()
    low = text.lower()
    q_error = (q_error or "").strip()

    if crashed:
        hint = (
            "yt-dlp did not finish normally (crashed or failed to start). "
            "Try again or update yt-dlp on your PATH; security software sometimes blocks in-place updates."
        )
        if q_error:
            return (f"{hint} Details: {q_error}"[:200], 10000)
        return (hint[:200], 10000)

    if exit_code != 0:
        if "pip" in low and ("pypi" in low or "wheel" in low):
            return (
                "This yt-dlp was installed with pip/PyPI; it cannot self-update from this button. "
                "Run: pip install -U yt-dlp",
                14000,
            )
        if "package manager" in low or "manual build" in low:
            return (
                "This yt-dlp was not installed as a standalone self-updating build. "
                "Upgrade it the same way you installed it (winget, scoop, brew, etc.).",
                14000,
            )
        for line in text.splitlines():
            s = line.strip()
            if s.upper().startswith("ERROR"):
                return (f"yt-dlp: {s[:110]}", 11000)
        line0 = text.splitlines()[0].strip() if text else ""
        tail = line0 or f"exit code {exit_code}"
        return (f"yt-dlp update did not succeed ({tail[:75]})", 10000)

    if "up to date" in low or "is up to date" in low or "already at the latest" in low:
        return ("yt-dlp is already up to date; no download was needed.", 6000)
    if "updated yt-dlp" in low or "successfully installed" in low or " updated to" in low:
        return ("A newer yt-dlp was installed. Restart this application if downloads still behave oddly.", 9000)
    if text:
        logger.info("yt-dlp -U (exit 0) output: %s", text[:800])
    return ("yt-dlp update check finished successfully.", 6000)


class SelfUpdateService(QtCore.QObject):
    """Wraps `yt-dlp -U` in a QProcess and reports (message, duration_ms) when it finishes."""

    finished_with_message = QtCore.Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: QtCore.QProcess | None = None
        self._reported = False

    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QtCore.QProcess.ProcessState.NotRunning

    def start(self) -> None:
        if self.is_running():
            return
        self._reported = False
        self._process = QtCore.QProcess(self)
        self._process.setProgram(yt_dlp_args.yt_dlp_program())
        self._process.setArguments(["-U"])
        self._process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self._process.errorOccurred.connect(self._on_error)
        self._process.finished.connect(self._on_finished)
        self._process.start()

    def _emit_finished(self, msg: str, duration_ms: int) -> None:
        """Emit finished_with_message once; ignore late finished/error after cleanup."""
        if self._reported:
            return
        self._reported = True
        proc = self._process
        self._process = None
        if proc is not None:
            proc.blockSignals(True)
            proc.deleteLater()
        self.finished_with_message.emit(msg, duration_ms)

    def _on_error(self, error: QtCore.QProcess.ProcessError) -> None:
        # FailedToStart does not reliably emit finished; other errors usually do.
        if error != QtCore.QProcess.ProcessError.FailedToStart:
            return
        proc = self._process
        if proc is None or self._reported:
            return
        q_err = proc.errorString()
        msg, duration_ms = status_message("", 1, True, q_err)
        logger.warning("yt-dlp -U failed to start: %s", q_err)
        self._emit_finished(msg, duration_ms)

    def _on_finished(self, exit_code: int, exit_status) -> None:
        proc = self._process
        if proc is None or self._reported:
            return
        combined = proc.readAllStandardOutput().data().decode("utf-8", errors="replace").strip()
        crashed = exit_status != QtCore.QProcess.ExitStatus.NormalExit
        q_err = proc.errorString() if crashed else ""
        msg, duration_ms = status_message(combined, exit_code, crashed, q_err)
        if exit_code != 0 or crashed:
            logger.warning("yt-dlp -U finished: exit=%s crashed=%s output=%r", exit_code, crashed, combined[:2000])
        else:
            logger.info("yt-dlp -U finished OK")
        self._emit_finished(msg, duration_ms)

    def shutdown(self) -> None:
        proc = self._process
        self._process = None
        self._reported = True
        if proc is not None:
            proc.blockSignals(True)
            if proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                proc.kill()
                proc.waitForFinished(5000)
            proc.deleteLater()
