from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class UrlInputPanel(QtWidgets.QWidget):
    add_clicked = QtCore.Signal()
    debounced_url_changed = QtCore.Signal()
    path_changed = QtCore.Signal()
    playlist_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lb_link = QtWidgets.QLabel("Video URL(s)")
        self.te_link = QtWidgets.QPlainTextEdit()
        self.te_link.setPlaceholderText(
            "https://www.youtube.com/watch?v=hTWKbfoikeg\n"
            "https://www.youtube.com/watch?v=KQetemT1sWc\n"
            "https://www.youtube.com/watch?v=yKNxeF4KMsY"
        )
        layout.addWidget(self.lb_link, 0, 0)
        layout.addWidget(self.te_link, 0, 1, 1, 4)

        self.pb_playlist = QtWidgets.QPushButton()
        self.pb_playlist.setVisible(False)
        layout.addWidget(self.pb_playlist, 1, 1, 1, 4)

        self.lb_path = QtWidgets.QLabel("Save to")
        self.le_path = QtWidgets.QLineEdit()
        self.le_path.setReadOnly(True)
        self.pb_path = QtWidgets.QPushButton("Browse...")
        self.pb_add = QtWidgets.QPushButton("Add")
        layout.addWidget(self.lb_path, 2, 0)
        layout.addWidget(self.le_path, 2, 1)
        layout.addWidget(self.pb_path, 2, 2)
        layout.addWidget(self.pb_add, 2, 4)

        layout.setColumnStretch(1, 5)

        self.pb_path.clicked.connect(self._browse)
        self.pb_add.clicked.connect(self.add_clicked.emit)
        self.pb_playlist.clicked.connect(self.playlist_clicked.emit)

        self._debounce = QtCore.QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(400)
        self._debounce.timeout.connect(self.debounced_url_changed.emit)
        self.te_link.textChanged.connect(self._debounce.start)

    def _browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select a folder",
            self.le_path.text() or QtCore.QDir.homePath(),
            QtWidgets.QFileDialog.Option.ShowDirsOnly,
        )
        if path:
            self.le_path.setText(path)
            self.path_changed.emit()

    def urls(self) -> list[str]:
        return [u.strip() for u in self.te_link.toPlainText().split("\n") if u.strip()]

    def first_url(self) -> str:
        urls = self.urls()
        return urls[0] if urls else ""

    def clear_urls(self) -> None:
        self.te_link.clear()

    def set_urls(self, urls: list[str]) -> None:
        self.te_link.setPlainText("\n".join(urls))

    def destination(self) -> str:
        return self.le_path.text().strip()

    def set_destination(self, path: str) -> None:
        self.le_path.setText(path)

    def set_playlist_detected(self, detected: bool, count: int = 0) -> None:
        if detected:
            self.pb_playlist.setText(f"Playlist detected ({count} videos) — click to choose which to add")
        self.pb_playlist.setVisible(detected)
