from __future__ import annotations

import logging
import os
import sys

from PySide6 import QtWidgets

from .services import config_store, dependency_check, exception_handler, paths


def _setup_logging() -> None:
    handlers = [logging.FileHandler(paths.debug_log_path(), encoding="utf-8", delay=True)]
    if not paths.is_frozen():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s (%(module)s:%(lineno)d) %(message)s",
        handlers=handlers,
    )
    if os.environ.get("YT_DLP_GUI_DEBUG", "").strip() in ("1", "true", "yes"):
        logging.getLogger().setLevel(logging.DEBUG)


def main() -> int:
    _setup_logging()
    logger = logging.getLogger(__name__)
    exception_handler.install()

    app = QtWidgets.QApplication(sys.argv)

    status = dependency_check.check_dependencies()
    if not status.ok:
        QtWidgets.QMessageBox.critical(
            None,
            "Missing required tools",
            "These programs must be installed and available on your PATH:\n\n"
            + "\n".join(f"  • {m}" for m in status.missing_required)
            + "\n\nInstall ffmpeg (including ffprobe) and yt-dlp, add them to PATH, "
            "then restart this application.",
        )
        logger.error("Missing PATH dependencies: %s", ", ".join(status.missing_required))
        return 1

    if not status.js_runtime_available:
        QtWidgets.QMessageBox.warning(
            None,
            "JavaScript runtime recommended",
            "No JavaScript runtime (Deno, Node.js, or Bun) was found on your PATH.\n\n"
            "YouTube may require one for its n-challenge; downloads can fail without it. "
            "Install Deno, Node.js, or Bun, then restart this application.\n\n"
            "You can continue without it for other sites.",
        )
        logger.warning("No JS runtime (deno/node/bun) on PATH; YouTube n-challenge may fail")

    try:
        config = config_store.load_config()
    except config_store.ConfigError as e:
        QtWidgets.QMessageBox.critical(None, "Configuration error", str(e))
        logger.exception("Failed to load config")
        return 1

    try:
        from .ui.main_window import MainWindow

        window = MainWindow(config)
        window.show()
    except Exception:
        logger.exception("Failed to start main window")
        QtWidgets.QMessageBox.critical(
            None,
            "Startup error",
            f"The application failed to start. Details were written to:\n{paths.debug_log_path()}",
        )
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
