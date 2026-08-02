from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ...models.format_spec import FormatSpec
from ...services import yt_dlp_args


class FormatOptionsPanel(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, presets: dict, parent=None):
        super().__init__(parent)
        self._video_info: dict | None = None
        self._video_info_url = ""
        self._presets: dict = {}
        # Saved when entering subtitle lock; restored on unlock. None means unlocked.
        self._pre_subtitle_lock: dict | None = None

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lb_file_type = QtWidgets.QLabel("Type")
        self.dd_file_type = QtWidgets.QComboBox()
        self.dd_file_type.addItem("Video", "video")
        self.dd_file_type.addItem("Audio", "audio")

        self.lb_container = QtWidgets.QLabel("Container")
        self.dd_container = QtWidgets.QComboBox()

        self.lb_quality = QtWidgets.QLabel("Quality")
        self.dd_quality = QtWidgets.QComboBox()
        self.dd_quality.setMinimumWidth(140)

        self.cb_use_saved_preset = QtWidgets.QCheckBox("Use saved preset")
        self.dd_saved_preset = QtWidgets.QComboBox()
        self.dd_saved_preset.setEnabled(False)
        self.dd_saved_preset.setMinimumWidth(120)

        for w in (self.lb_file_type, self.dd_file_type, self.lb_container, self.dd_container, self.lb_quality):
            layout.addWidget(w)
        layout.addWidget(self.dd_quality, 1)
        layout.addWidget(self.cb_use_saved_preset)
        layout.addWidget(self.dd_saved_preset)

        self._manual_widgets = (
            self.dd_file_type,
            self.dd_container,
            self.dd_quality,
            self.lb_file_type,
            self.lb_container,
            self.lb_quality,
        )

        self.set_presets(presets)

        self.dd_file_type.currentIndexChanged.connect(self._on_file_type_changed)
        self.cb_use_saved_preset.toggled.connect(self._on_use_saved_toggled)
        self._on_file_type_changed()

    def set_presets(self, presets: dict) -> None:
        self._presets = dict(presets)
        self.dd_saved_preset.blockSignals(True)
        self.dd_saved_preset.clear()
        self.dd_saved_preset.addItems(list(self._presets.keys()))
        self.dd_saved_preset.blockSignals(False)

    def set_current_preset_index(self, idx: int) -> None:
        if 0 <= idx < self.dd_saved_preset.count():
            self.dd_saved_preset.setCurrentIndex(idx)

    def current_preset_index(self) -> int:
        return self.dd_saved_preset.currentIndex()

    def set_use_saved_preset(self, checked: bool) -> None:
        self.cb_use_saved_preset.setChecked(checked)

    def _populate_containers(self, file_type: str, *, mkv_first: bool = False) -> None:
        self.dd_container.blockSignals(True)
        self.dd_container.clear()
        if file_type == "audio":
            items = (("MP3", "mp3"), ("WAV", "wav"), ("M4A (AAC)", "m4a"))
        elif mkv_first:
            items = (("MKV", "mkv"), ("MP4", "mp4"), ("WebM", "webm"))
        else:
            items = (("MP4", "mp4"), ("MKV", "mkv"), ("WebM", "webm"))
        for label, key in items:
            self.dd_container.addItem(label, key)
        self.dd_container.blockSignals(False)

    def _select_by_data(self, combo: QtWidgets.QComboBox, data, default_index: int = 0) -> None:
        idx = combo.findData(data)
        if idx < 0 and data is not None:
            for i in range(combo.count()):
                if combo.itemData(i) == data:
                    idx = i
                    break
        combo.setCurrentIndex(idx if idx >= 0 else default_index)

    def _on_file_type_changed(self, *_args) -> None:
        ft = self.dd_file_type.currentData() or "video"
        self._populate_containers(ft, mkv_first=False)
        self.dd_container.blockSignals(True)
        self.dd_container.setCurrentIndex(0)
        self.dd_container.blockSignals(False)
        self._repopulate_quality()
        self.changed.emit()

    def _repopulate_quality(self, *, preserve: bool = False) -> None:
        prev = self.dd_quality.currentData() if preserve else None
        self.dd_quality.blockSignals(True)
        self.dd_quality.clear()
        self.dd_quality.addItem("Best", ("best", None))
        ft = self.dd_file_type.currentData() or "video"
        if ft != "audio":
            info = self._video_info if isinstance(self._video_info, dict) else None
            for h in yt_dlp_args.video_heights_from_info(info):
                self.dd_quality.addItem(f"{h}p (max)", ("height_cap", h))
        if preserve and prev is not None:
            self._select_by_data(self.dd_quality, prev, default_index=0)
        else:
            self.dd_quality.setCurrentIndex(0)
        self.dd_quality.blockSignals(False)

    def set_video_info(self, url: str, info: dict | None) -> None:
        self._video_info = info
        self._video_info_url = url
        self._repopulate_quality(preserve=True)

    def _on_use_saved_toggled(self, checked: bool) -> None:
        self.dd_saved_preset.setEnabled(checked)
        for w in self._manual_widgets:
            w.setEnabled(not checked)
        self.changed.emit()

    def lock_for_subtitles(self, locked: bool) -> None:
        """Subtitles require an MKV merge; force that container and disable presets while locked."""
        if locked:
            # Re-lock (e.g. changing subtitle language) must not reset quality/container state.
            if self._pre_subtitle_lock is not None:
                return
            self._pre_subtitle_lock = {
                "use_saved": self.cb_use_saved_preset.isChecked(),
                "preset_index": self.dd_saved_preset.currentIndex(),
                "file_type": self.dd_file_type.currentData() or "video",
                "container": self.dd_container.currentData(),
                "quality": self.dd_quality.currentData(),
            }
            was_video = (self.dd_file_type.currentData() or "video") == "video"
            self.cb_use_saved_preset.blockSignals(True)
            self.cb_use_saved_preset.setChecked(False)
            self.cb_use_saved_preset.blockSignals(False)
            self.cb_use_saved_preset.setEnabled(False)
            self.dd_saved_preset.setEnabled(False)
            for w in self._manual_widgets:
                w.setEnabled(False)
            self.dd_file_type.blockSignals(True)
            self.dd_file_type.setCurrentIndex(0)
            self.dd_file_type.blockSignals(False)
            self._populate_containers("video", mkv_first=True)
            self.dd_container.blockSignals(True)
            self.dd_container.setCurrentIndex(0)  # MKV
            self.dd_container.blockSignals(False)
            if not was_video:
                self._repopulate_quality()
                self.dd_quality.blockSignals(True)
                self._select_by_data(self.dd_quality, self._pre_subtitle_lock.get("quality"), default_index=0)
                self.dd_quality.blockSignals(False)
        else:
            saved = self._pre_subtitle_lock
            self._pre_subtitle_lock = None
            self.cb_use_saved_preset.setEnabled(True)
            if saved is not None:
                ft = saved.get("file_type") or "video"
                self.dd_file_type.blockSignals(True)
                self._select_by_data(self.dd_file_type, ft, default_index=0)
                self.dd_file_type.blockSignals(False)
                self._populate_containers(ft, mkv_first=False)
                self.dd_container.blockSignals(True)
                self._select_by_data(self.dd_container, saved.get("container"), default_index=0)
                self.dd_container.blockSignals(False)
                self._repopulate_quality()
                self.dd_quality.blockSignals(True)
                self._select_by_data(self.dd_quality, saved.get("quality"), default_index=0)
                self.dd_quality.blockSignals(False)
                self.cb_use_saved_preset.blockSignals(True)
                self.cb_use_saved_preset.setChecked(bool(saved.get("use_saved")))
                self.cb_use_saved_preset.blockSignals(False)
                pidx = saved.get("preset_index", 0)
                if isinstance(pidx, int) and 0 <= pidx < self.dd_saved_preset.count():
                    self.dd_saved_preset.setCurrentIndex(pidx)
            self._on_use_saved_toggled(self.cb_use_saved_preset.isChecked())

    def use_saved_preset(self) -> bool:
        return self.cb_use_saved_preset.isChecked()

    def selected_preset_key(self) -> str:
        return self.dd_saved_preset.currentText()

    def _current_quality_tuple(self):
        data = self.dd_quality.currentData()
        if isinstance(data, (list, tuple)) and len(data) >= 1:
            return data[0], (data[1] if len(data) > 1 else None)
        return "best", None

    def build_format_spec(self, url: str, presets: dict) -> FormatSpec | None:
        """Returns None if "use saved preset" is on but no valid preset is selected."""
        if self.use_saved_preset():
            preset_key = self.selected_preset_key()
            if preset_key not in presets:
                return None
            argv = yt_dlp_args.resolve_preset_argv(preset_key, url, presets)
            return FormatSpec(mode="preset", preset_key=preset_key, resolved_argv=argv)
        ft = self.dd_file_type.currentData() or "video"
        cont = self.dd_container.currentData() or "mp4"
        q_mode, q_h = self._current_quality_tuple()
        argv = yt_dlp_args.build_manual_format_argv(ft, cont, q_mode, q_h, url)
        return FormatSpec(
            mode="manual", file_type=ft, container=cont, quality_mode=q_mode, max_height=q_h, resolved_argv=argv
        )
