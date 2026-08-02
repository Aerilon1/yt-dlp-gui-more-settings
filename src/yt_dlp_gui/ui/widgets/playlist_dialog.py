from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ...models.playlist_entry import PlaylistEntry


class PlaylistDialog(QtWidgets.QDialog):
    """Lets the user pick all/none/a range/individual entries from a probed playlist or channel."""

    def __init__(self, entries: list[PlaylistEntry], playlist_title: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Select videos — {playlist_title}" if playlist_title else "Select videos")
        self.resize(560, 440)

        layout = QtWidgets.QVBoxLayout(self)

        btn_row = QtWidgets.QHBoxLayout()
        self.pb_select_all = QtWidgets.QPushButton("Select all")
        self.pb_select_none = QtWidgets.QPushButton("Select none")
        self.lb_range = QtWidgets.QLabel("Range:")
        self.sp_from = QtWidgets.QSpinBox()
        self.sp_from.setRange(1, max(1, len(entries)))
        self.sp_to = QtWidgets.QSpinBox()
        self.sp_to.setRange(1, max(1, len(entries)))
        self.sp_to.setValue(max(1, len(entries)))
        self.pb_apply_range = QtWidgets.QPushButton("Apply range")
        for w in (self.pb_select_all, self.pb_select_none, self.lb_range, self.sp_from, self.sp_to, self.pb_apply_range):
            btn_row.addWidget(w)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.list_widget = QtWidgets.QListWidget()
        for entry in entries:
            text = f"{entry.index}. {entry.title}"
            if entry.duration_text:
                text += f"  ({entry.duration_text})"
            item = QtWidgets.QListWidgetItem(text)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Checked if entry.selected else QtCore.Qt.CheckState.Unchecked)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.pb_select_all.clicked.connect(lambda: self._set_all(True))
        self.pb_select_none.clicked.connect(lambda: self._set_all(False))
        self.pb_apply_range.clicked.connect(self._apply_range)

    def _set_all(self, checked: bool) -> None:
        state = QtCore.Qt.CheckState.Checked if checked else QtCore.Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def _apply_range(self) -> None:
        lo, hi = self.sp_from.value(), self.sp_to.value()
        if lo > hi:
            lo, hi = hi, lo
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            entry: PlaylistEntry = item.data(QtCore.Qt.ItemDataRole.UserRole)
            item.setCheckState(
                QtCore.Qt.CheckState.Checked if lo <= entry.index <= hi else QtCore.Qt.CheckState.Unchecked
            )

    def selected_entries(self) -> list[PlaylistEntry]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                result.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        return result
