from PySide6 import QtCore, QtWidgets

from yt_dlp_gui.services.self_update_service import SelfUpdateService, status_message


def test_crashed():
    msg, ms = status_message("", 1, True, "process failed to start")
    assert "did not finish normally" in msg
    assert "process failed to start" in msg


def test_failed_to_start_emits_once_and_clears_running():
    """FailedToStart must emit finished_with_message so Update re-enables (no double-emit)."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])

    svc = SelfUpdateService()
    messages: list[tuple[str, int]] = []
    svc.finished_with_message.connect(lambda m, d: messages.append((m, d)))

    svc._reported = False
    svc._process = QtCore.QProcess(svc)

    svc._on_error(QtCore.QProcess.ProcessError.FailedToStart)
    assert len(messages) == 1
    assert "did not finish normally" in messages[0][0]
    assert svc._process is None
    assert not svc.is_running()

    # A late finished must not double-emit.
    svc._on_finished(1, QtCore.QProcess.ExitStatus.CrashExit)
    assert len(messages) == 1


def test_pip_installed_cannot_self_update():
    msg, ms = status_message("ERROR: You installed yt-dlp with pip or using the wheel from PyPI", 1, False, "")
    assert "pip install -U yt-dlp" in msg


def test_package_manager_installed():
    msg, ms = status_message("This build was built by a package manager", 1, False, "")
    assert "winget, scoop, brew" in msg


def test_generic_error_line_extracted():
    msg, ms = status_message("some noise\nERROR: network unreachable\nmore noise", 1, False, "")
    assert "network unreachable" in msg


def test_up_to_date():
    msg, ms = status_message("yt-dlp is up to date (2024.01.01)", 0, False, "")
    assert "already up to date" in msg


def test_updated_successfully():
    msg, ms = status_message("Updated yt-dlp to 2024.02.02", 0, False, "")
    assert "newer yt-dlp was installed" in msg


def test_success_no_notable_output():
    msg, ms = status_message("", 0, False, "")
    assert "finished successfully" in msg
