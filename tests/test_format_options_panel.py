"""Tests for FormatOptionsPanel subtitle lock/unlock state restore."""
from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from yt_dlp_gui.ui.widgets.format_options_panel import FormatOptionsPanel

_VIDEO_INFO = {
    "formats": [
        {"height": 1080, "vcodec": "avc1"},
        {"height": 720, "vcodec": "avc1"},
    ]
}


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _select_quality(panel: FormatOptionsPanel, height: int) -> None:
    panel.set_video_info("https://example.com/v", _VIDEO_INFO)
    for i in range(panel.dd_quality.count()):
        data = panel.dd_quality.itemData(i)
        if isinstance(data, (list, tuple)) and len(data) >= 2 and data == ("height_cap", height):
            panel.dd_quality.setCurrentIndex(i)
            return
    raise AssertionError(f"quality {height}p not in dropdown")


def test_lock_unlock_restores_mp4_container(qapp):
    panel = FormatOptionsPanel({"best": "-f best"})
    assert panel.dd_container.currentData() == "mp4"

    panel.lock_for_subtitles(True)
    assert panel.dd_container.currentData() == "mkv"

    panel.lock_for_subtitles(False)
    assert panel.dd_container.currentData() == "mp4"
    assert panel.dd_container.itemText(0) == "MP4"


def test_relock_preserves_quality(qapp):
    panel = FormatOptionsPanel({"best": "-f best"})
    _select_quality(panel, 720)
    assert panel.dd_quality.currentData() == ("height_cap", 720)

    panel.lock_for_subtitles(True)
    assert panel.dd_quality.currentData() == ("height_cap", 720)

    # Re-lock (e.g. subtitle language change) must not reset quality.
    panel.lock_for_subtitles(True)
    assert panel.dd_quality.currentData() == ("height_cap", 720)

    panel.lock_for_subtitles(False)
    assert panel.dd_quality.currentData() == ("height_cap", 720)


def test_lock_unlock_restores_saved_preset(qapp):
    panel = FormatOptionsPanel({"best": "-f best", "mkv": "-f best --merge-output-format mkv"})
    panel.set_use_saved_preset(True)
    panel.set_current_preset_index(1)

    panel.lock_for_subtitles(True)
    assert not panel.use_saved_preset()

    panel.lock_for_subtitles(False)
    assert panel.use_saved_preset()
    assert panel.selected_preset_key() == "mkv"
