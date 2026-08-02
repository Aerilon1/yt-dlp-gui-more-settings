from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ...models.history_entry import HistoryEntry
from ...services.history_store import HistoryStore

COLUMNS = ("Title", "URL", "Status", "Started", "Destination")


class HistoryPanel(QtWidgets.QWidget):
    redownload_requested = QtCore.Signal(object)  # HistoryEntry

    def __init__(self, history_store: HistoryStore, parent=None):
        super().__init__(parent)
        self._store = history_store
        self._entries: list[HistoryEntry] = []

        layout = QtWidgets.QVBoxLayout(self)
        search_row = QtWidgets.QHBoxLayout()
        self.le_search = QtWidgets.QLineEdit()
        self.le_search.setPlaceholderText("Search title or URL…")
        search_row.addWidget(self.le_search)
        layout.addLayout(search_row)

        self.table = QtWidgets.QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.table, 1)

        self.le_search.textChanged.connect(self.refresh)
        self.table.customContextMenuRequested.connect(self._open_menu)

        self.refresh()

    def refresh(self) -> None:
        query = self.le_search.text()
        self._entries = self._store.search(query)
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(entry.title))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(entry.url))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(entry.status))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(entry.started_at))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(entry.destination_dir))

    def _open_menu(self, position: QtCore.QPoint) -> None:
        row = self.table.rowAt(position.y())
        if row < 0 or row >= len(self._entries):
            return
        entry = self._entries[row]
        menu = QtWidgets.QMenu(self)
        open_action = menu.addAction("Open containing folder")
        redownload_action = menu.addAction("Re-download")
        action = menu.exec(self.table.viewport().mapToGlobal(position))
        if action == open_action:
            if entry.destination_dir:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(entry.destination_dir))
        elif action == redownload_action:
            self.redownload_requested.emit(entry)
