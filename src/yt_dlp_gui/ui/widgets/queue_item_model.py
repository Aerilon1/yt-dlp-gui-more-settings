"""QAbstractTableModel wrapping the DownloadManager's items -- replaces the pre-rewrite
app's QTreeWidget + Qt.UserRole-smuggled item data with a real Qt model."""
from __future__ import annotations

from PySide6 import QtCore

from ...models.download_item import DownloadItem

COLUMNS = ("Title", "Format", "Size", "Progress", "Status", "Speed", "ETA")
COL_TITLE, COL_FORMAT, COL_SIZE, COL_PROGRESS, COL_STATUS, COL_SPEED, COL_ETA = range(7)

ItemRole = QtCore.Qt.ItemDataRole.UserRole + 1


class QueueTableModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[DownloadItem] = []
        self._row_by_id: dict[int, int] = {}

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if role == QtCore.Qt.ItemDataRole.DisplayRole and orientation == QtCore.Qt.Orientation.Horizontal:
            return COLUMNS[section]
        return None

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        col = index.column()
        if role == ItemRole:
            return item
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole and col != COL_TITLE:
            return QtCore.Qt.AlignmentFlag.AlignCenter
        if role != QtCore.Qt.ItemDataRole.DisplayRole:
            return None
        if col == COL_TITLE:
            return item.title or item.url
        if col == COL_FORMAT:
            return item.queue_label()
        if col == COL_SIZE:
            return item.size_text
        if col == COL_PROGRESS:
            return item.percent_text
        if col == COL_STATUS:
            return item.status_text
        if col == COL_SPEED:
            return item.speed_text
        if col == COL_ETA:
            return item.eta_text
        return None

    def item_at(self, row: int) -> DownloadItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def add_item(self, item: DownloadItem) -> None:
        row = len(self._items)
        self.beginInsertRows(QtCore.QModelIndex(), row, row)
        self._items.append(item)
        self._row_by_id[item.id] = row
        self.endInsertRows()

    def update_item(self, item_id: int, fields: dict) -> None:
        row = self._row_by_id.get(item_id)
        if row is None:
            return
        left = self.index(row, 0)
        right = self.index(row, len(COLUMNS) - 1)
        self.dataChanged.emit(left, right)

    def remove_item(self, item_id: int) -> None:
        row = self._row_by_id.get(item_id)
        if row is None:
            return
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        del self._items[row]
        del self._row_by_id[item_id]
        for iid, r in self._row_by_id.items():
            if r > row:
                self._row_by_id[iid] = r - 1
        self.endRemoveRows()
