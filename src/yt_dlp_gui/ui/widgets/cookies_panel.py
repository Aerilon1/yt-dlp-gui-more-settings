from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class CookiesPanel(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lb_cookies = QtWidgets.QLabel("Cookies file")
        self.le_cookies_file = QtWidgets.QLineEdit()
        self.le_cookies_file.setPlaceholderText("Path to cookies.txt, or empty for cookies.txt in app data folder")
        self.pb_browse = QtWidgets.QPushButton("Browse…")
        layout.addWidget(self.lb_cookies)
        layout.addWidget(self.le_cookies_file, 1)
        layout.addWidget(self.pb_browse)
        self.lb_cookies.setToolTip(
            "Optional Netscape-format cookies file. Leave empty to use cookies.txt in the "
            "app's user data folder."
        )
        self.pb_browse.clicked.connect(self._on_browse)
        self.le_cookies_file.editingFinished.connect(self.changed.emit)

    def _on_browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select cookies file",
            self.le_cookies_file.text() or QtCore.QDir.homePath(),
            "Text files (*.txt);;All files (*.*)",
        )
        if path:
            self.le_cookies_file.setText(path)
            self.changed.emit()

    def set_path(self, path: str) -> None:
        self.le_cookies_file.setText(path)

    def path(self) -> str:
        return self.le_cookies_file.text().strip()
