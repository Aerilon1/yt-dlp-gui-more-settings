from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ...models.download_item import DownloadState
from ..icons import icon
from .progress_delegate import ProgressBarDelegate
from .queue_item_model import COL_PROGRESS, ItemRole, QueueTableModel


class QueueView(QtWidgets.QTableView):
    retry_requested = QtCore.Signal(int)
    cancel_requested = QtCore.Signal(int)
    remove_requested = QtCore.Signal(int)
    status_message = QtCore.Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_ = QueueTableModel(self)
        self.setModel(self.model_)
        self.setItemDelegateForColumn(COL_PROGRESS, ProgressBarDelegate(self))
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._open_menu)

    def _open_menu(self, position: QtCore.QPoint) -> None:
        index = self.indexAt(position)
        if not index.isValid():
            return
        item = index.data(ItemRole)
        if item is None:
            return

        menu = QtWidgets.QMenu(self)
        delete_action = menu.addAction(icon("mdi6.trash-can"), "Delete")
        copy_action = menu.addAction(icon("mdi6.content-copy"), "Copy URL")
        open_action = menu.addAction(icon("mdi6.folder-open"), "Open Folder")
        retry_action = None
        cancel_action = None
        if item.state in (DownloadState.ERROR, DownloadState.CANCELLED):
            retry_action = menu.addAction(icon("mdi6.refresh"), "Retry")
        if item.state in (DownloadState.QUEUED, DownloadState.DOWNLOADING):
            cancel_action = menu.addAction(icon("mdi6.close-circle-outline"), "Cancel")

        action = menu.exec(self.viewport().mapToGlobal(position))
        if action == delete_action:
            self.remove_requested.emit(item.id)
        elif action == copy_action:
            QtWidgets.QApplication.clipboard().setText(item.url)
        elif action == open_action:
            if not item.destination_dir:
                self.status_message.emit("This row has no save folder set.", 5000)
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(item.destination_dir))
        elif cancel_action is not None and action == cancel_action:
            self.cancel_requested.emit(item.id)
        elif retry_action is not None and action == retry_action:
            self.retry_requested.emit(item.id)
