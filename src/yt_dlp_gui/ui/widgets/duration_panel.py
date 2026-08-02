from __future__ import annotations

import re

from PySide6 import QtWidgets

# yt-dlp --download-sections TIME: [[HH:]MM:]SS[.ms] or inf
_TIME_RE = re.compile(r"^(?:inf|(?:\d+:){0,2}\d+(?:\.\d+)?)$", re.IGNORECASE)


def _parse_seconds(value: str) -> float | None:
    """Parse a yt-dlp-ish time to seconds, or None if invalid."""
    text = value.strip()
    if not text or not _TIME_RE.fullmatch(text):
        return None
    if text.lower() == "inf":
        return float("inf")
    parts = text.split(":")
    try:
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None


class DurationPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cb_custom_duration = QtWidgets.QCheckBox("Custom duration")
        self.lb_start = QtWidgets.QLabel("Start")
        self.le_start = QtWidgets.QLineEdit()
        self.le_start.setPlaceholderText("0:00")
        self.le_start.setToolTip("Start time as [[HH:]MM:]SS or seconds (e.g. 0:00, 90, 1:02:03)")
        self.lb_end = QtWidgets.QLabel("End")
        self.le_end = QtWidgets.QLineEdit()
        self.le_end.setPlaceholderText("1:30 or inf")
        self.le_end.setToolTip("End time as [[HH:]MM:]SS, seconds, or inf for end of video")
        for w in (self.cb_custom_duration, self.lb_start, self.le_start, self.lb_end, self.le_end):
            layout.addWidget(w)
        self.cb_custom_duration.toggled.connect(self._on_toggled)
        self._on_toggled(False)

    def _on_toggled(self, checked: bool) -> None:
        for w in (self.lb_start, self.le_start, self.lb_end, self.le_end):
            w.setEnabled(checked)

    def is_enabled(self) -> bool:
        return self.cb_custom_duration.isChecked()

    @staticmethod
    def _format_section(start: str, end: str) -> str:
        """yt-dlp --download-sections value: time range, not chapter (leading *)."""
        s, e = start.strip(), end.strip()
        return f"*{s}-{e}" if s and e else ""

    def has_valid_range(self) -> bool:
        if not self.is_enabled():
            return True
        start_s = _parse_seconds(self.le_start.text())
        end_s = _parse_seconds(self.le_end.text())
        if start_s is None or end_s is None:
            return False
        return start_s < end_s

    def download_section(self) -> str:
        if not self.is_enabled() or not self.has_valid_range():
            return ""
        return self._format_section(self.le_start.text(), self.le_end.text())
