"""
Global exception handler. The pre-rewrite app had none: since it's built as a windowed
(console=False) executable, an unhandled exception in a button handler or async callback
had nowhere to print to and could silently kill the whole GUI. Installing sys.excepthook
covers exceptions raised inside Qt slots (PySide6 routes those through excepthook); the
caller is still responsible for wrapping pre-event-loop startup code in its own try/except,
since excepthook alone can't help before QApplication exists.
"""
from __future__ import annotations

import logging
import sys
import traceback

from . import paths

logger = logging.getLogger(__name__)


def install() -> None:
    sys.excepthook = _handle_exception


def _handle_exception(exc_type, exc_value, exc_tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error("Unhandled exception:\n%s", text)
    _show_dialog(exc_value)


def _show_dialog(exc_value: BaseException) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
    except Exception:
        return
    if QApplication.instance() is None:
        return
    try:
        QMessageBox.critical(
            None,
            "Unexpected error",
            "An unexpected error occurred:\n\n"
            f"{exc_value}\n\n"
            f"Details were written to:\n{paths.debug_log_path()}",
        )
    except Exception:
        logger.exception("Failed to show exception dialog")
