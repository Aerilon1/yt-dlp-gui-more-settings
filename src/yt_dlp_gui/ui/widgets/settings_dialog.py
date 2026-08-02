from __future__ import annotations

from PySide6 import QtWidgets

from ...services.config_store import AppConfig


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")

        form = QtWidgets.QFormLayout(self)

        self.sp_concurrency = QtWidgets.QSpinBox()
        self.sp_concurrency.setRange(1, 10)
        self.sp_concurrency.setValue(config.max_concurrent_downloads)
        form.addRow("Max simultaneous downloads", self.sp_concurrency)

        self.sp_retry = QtWidgets.QSpinBox()
        self.sp_retry.setRange(0, 10)
        self.sp_retry.setValue(config.retry_count)
        form.addRow("Retries on failure", self.sp_retry)

        self.cb_precise_cuts = QtWidgets.QCheckBox("Precise section cuts (slower re-encode)")
        self.cb_precise_cuts.setChecked(config.precise_section_cuts)
        form.addRow(self.cb_precise_cuts)

        self.le_global_args = QtWidgets.QLineEdit(config.global_args)
        form.addRow("Extra yt-dlp arguments", self.le_global_args)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply_to(self, config: AppConfig) -> None:
        config.max_concurrent_downloads = self.sp_concurrency.value()
        config.retry_count = self.sp_retry.value()
        config.precise_section_cuts = self.cb_precise_cuts.isChecked()
        config.global_args = self.le_global_args.text()
