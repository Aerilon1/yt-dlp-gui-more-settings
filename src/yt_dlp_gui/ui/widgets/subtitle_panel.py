"""
Subtitle selection UI. Keeps a small per-URL scan cache instead of a single "last scan"
slot: this is what fixes the pre-rewrite cross-item bug where scanning video B would
silently change which subtitle languages a retry of video A requested. Each queued item's
SubtitleSpec is built from *that item's own URL's* cache entry (or falls back to "en" if
its URL was never scanned), never from whichever URL happened to be scanned most recently.
"""
from __future__ import annotations

import json
import logging

from PySide6 import QtCore, QtWidgets

from ...models.subtitle_spec import SubtitleSpec
from ...services import probe_service

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "en": "English", "ja": "Japanese", "es": "Spanish", "fr": "French",
    "de": "German", "pt": "Portuguese", "ru": "Russian", "ko": "Korean",
    "zh": "Chinese", "zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)",
    "it": "Italian", "nl": "Dutch", "pl": "Polish", "ar": "Arabic",
    "hi": "Hindi", "tr": "Turkish", "vi": "Vietnamese", "th": "Thai",
}

_SCAN_CACHE_LIMIT = 20


def _lang_display_name(code: str) -> str:
    base = code.split("-")[0].split("_")[0] if code else ""
    return LANGUAGE_NAMES.get(base) or LANGUAGE_NAMES.get(code) or code


def _dedup_base_langs(codes) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for code in sorted(codes):
        if not code or not isinstance(code, str):
            continue
        base = code.split("-")[0].split("_")[0]
        if base in seen:
            continue
        seen.add(base)
        result.append(code)
    return result


class _ScanResult:
    __slots__ = ("manual_langs", "auto_langs")

    def __init__(self, manual_langs: list[str], auto_langs: list[str]):
        self.manual_langs = manual_langs
        self.auto_langs = auto_langs


class SubtitlePanel(QtWidgets.QWidget):
    changed = QtCore.Signal()
    status_message = QtCore.Signal(str, int)
    scan_clicked = QtCore.Signal()
    video_info_scanned = QtCore.Signal(str, object)  # url, info dict (reused for quality dropdown)

    def __init__(self, config_provider, parent=None):
        super().__init__(parent)
        self._config_provider = config_provider  # callable() -> AppConfig
        self._scan_cache: dict[str, _ScanResult] = {}
        self._scan_order: list[str] = []
        self._scan_thread: probe_service.ProbeThread | None = None
        self._scan_request_id = 0

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lb_subs = QtWidgets.QLabel("Subtitles")
        self.dd_subtitles = QtWidgets.QComboBox()
        self.dd_subtitles.setMinimumWidth(180)
        self.dd_subtitles.addItem("None", "")
        self.pb_scan_subs = QtWidgets.QPushButton("Scan subtitles")
        layout.addWidget(self.lb_subs)
        layout.addWidget(self.dd_subtitles, 1)
        layout.addWidget(self.pb_scan_subs)

        self.pb_scan_subs.clicked.connect(self.scan_clicked.emit)
        self.dd_subtitles.currentIndexChanged.connect(self.changed.emit)

    def is_enabled_mode(self) -> bool:
        return bool(self.dd_subtitles.currentData())

    def start_scan(self, url: str) -> None:
        url = (url or "").strip()
        if not url:
            self.status_message.emit("Paste a video URL first, then click Scan subtitles.", 5000)
            return
        self.pb_scan_subs.setEnabled(False)
        self.status_message.emit("Scanning subtitles…", 0)
        probe_service.abort_thread(self._scan_thread)
        self._scan_request_id += 1
        rid = self._scan_request_id
        thread = probe_service.ProbeThread(url, self._config_provider(), rid, flat_playlist=False, parent=self)
        self._scan_thread = thread
        thread.result_ready.connect(self._on_scan_finished)

        def _done(th=thread):
            if self._scan_thread is th:
                self.pb_scan_subs.setEnabled(True)

        thread.finished.connect(_done)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def abort_pending_scan(self, wait_ms: int = 3000) -> None:
        probe_service.abort_thread(self._scan_thread, wait_ms=wait_ms)

    def _on_scan_finished(self, request_id: int, url: str, json_str: str | None) -> None:
        if request_id != self._scan_request_id:
            return
        self.dd_subtitles.blockSignals(True)
        self.dd_subtitles.clear()
        if not json_str:
            self.dd_subtitles.addItem("None", "")
            self.dd_subtitles.blockSignals(False)
            self.changed.emit()
            self.status_message.emit("Could not list subtitles. Check the URL and try again.", 5000)
            return
        try:
            info = json.loads(json_str)
        except json.JSONDecodeError:
            self.dd_subtitles.addItem("None", "")
            self.dd_subtitles.blockSignals(False)
            self.changed.emit()
            self.status_message.emit("Could not parse subtitle info.", 5000)
            return

        subtitles = info.get("subtitles") or {}
        automatic_captions = info.get("automatic_captions") or {}
        manual_langs = _dedup_base_langs(subtitles.keys())
        auto_langs = _dedup_base_langs(automatic_captions.keys())
        self._remember_scan(url, manual_langs, auto_langs)

        # "All" modes only use manual subtitle langs (see docs/subtitle-process-and-issues.md).
        # Do not offer them when the scan found only automatic_captions — that used to fall
        # back to a single "en" track and looked like "all" worked.
        entries: list[tuple[str, str]] = [("None", "")]
        if manual_langs:
            entries.append(("All (all tracks)", "all_tracks"))
            entries.append(("All (subtitle files)", "all"))
            for code in manual_langs:
                name = _lang_display_name(code)
                label = f"{name} ({code})" if name != code else code
                entries.append((label, code))
        for code in auto_langs:
            name = _lang_display_name(code)
            label = f"{name} - auto ({code})" if name != code else f"Auto ({code})"
            entries.append((label, "auto:" + code))

        for label, value in entries:
            self.dd_subtitles.addItem(label, value)
        self.dd_subtitles.setCurrentIndex(0)
        self.dd_subtitles.blockSignals(False)
        self.changed.emit()
        self.video_info_scanned.emit(url, info)
        self.status_message.emit("Subtitles list updated.", 3000)

    def _remember_scan(self, url: str, manual_langs: list[str], auto_langs: list[str]) -> None:
        if url in self._scan_cache:
            self._scan_order.remove(url)
        self._scan_cache[url] = _ScanResult(manual_langs, auto_langs)
        self._scan_order.append(url)
        while len(self._scan_order) > _SCAN_CACHE_LIMIT:
            oldest = self._scan_order.pop(0)
            self._scan_cache.pop(oldest, None)

    def build_subtitle_spec(self, url: str) -> SubtitleSpec:
        """
        Build the SubtitleSpec for one specific item's URL. The selected mode (None/lang/All)
        applies uniformly to a batch by design (the user picked it once for "these videos"),
        but the concrete language list for "All" modes always comes from *this URL's own*
        scan-cache entry -- never from whichever URL was scanned most recently.
        """
        value = self.dd_subtitles.currentData() or ""
        if not value:
            return SubtitleSpec.none()
        if value in ("all_tracks", "all"):
            cached = self._scan_cache.get((url or "").strip())
            langs = list(cached.manual_langs) if cached else []
            if not langs:
                return SubtitleSpec.none()
            return SubtitleSpec(mode=value, langs=langs)
        if value.startswith("auto:"):
            lang = value.split(":", 1)[1].strip()
            return SubtitleSpec(mode="auto_lang", lang=lang or "en")
        return SubtitleSpec(mode="lang", lang=value or "en")
