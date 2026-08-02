from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from .queue_item_model import COL_PROGRESS


class ProgressBarDelegate(QtWidgets.QStyledItemDelegate):
    """Paints the Progress column as a real progress bar (percent, or a busy/indeterminate bar)."""

    def paint(self, painter, option, index) -> None:
        if index.column() != COL_PROGRESS:
            super().paint(painter, option, index)
            return
        text = str(index.data(QtCore.Qt.ItemDataRole.DisplayRole) or "-").strip()
        opt = QtWidgets.QStyleOptionProgressBar()
        opt.rect = option.rect.adjusted(2, 2, -2, -2)
        opt.minimum = 0
        opt.maximum = 100
        opt.textVisible = False
        if text.upper() == "INDETERMINATE":
            opt.maximum = 0
            opt.progress = 0
        elif text in ("-", ""):
            opt.progress = 0
        else:
            try:
                opt.progress = round(float(text.replace("%", "")))
            except ValueError:
                opt.progress = 0
        style = QtWidgets.QApplication.style()
        style.drawControl(QtWidgets.QStyle.ControlElement.CE_ProgressBar, opt, painter)
