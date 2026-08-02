"""Tests for SubtitlePanel spec building."""
from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from yt_dlp_gui.ui.widgets.subtitle_panel import SubtitlePanel


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_build_subtitle_spec_all_tracks_without_scan_returns_none(qapp):
    panel = SubtitlePanel(lambda: None)
    panel.dd_subtitles.clear()
    panel.dd_subtitles.addItem("None", "")
    panel.dd_subtitles.addItem("All (all tracks)", "all_tracks")
    panel.dd_subtitles.setCurrentIndex(1)

    spec = panel.build_subtitle_spec("https://example.com/v")
    assert not spec.enabled
