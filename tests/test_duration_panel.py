"""Tests for DurationPanel time validation ([[HH:]MM:]SS / inf)."""
from __future__ import annotations

import pytest
from PySide6 import QtWidgets

from yt_dlp_gui.ui.widgets.duration_panel import DurationPanel, _parse_seconds


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0", 0.0),
        ("90", 90.0),
        ("1:30", 90.0),
        ("1:02:03", 3723.0),
        ("1:02:03.5", 3723.5),
        ("inf", float("inf")),
        ("INF", float("inf")),
        ("Inf", float("inf")),
        ("", None),
        ("abc", None),
        ("  ", None),
        (":30", None),
        ("1:2:3:4", None),
    ],
)
def test_parse_seconds(text, expected):
    got = _parse_seconds(text)
    if expected is None:
        assert got is None
    elif expected == float("inf"):
        assert got == float("inf")
    else:
        assert got == pytest.approx(expected)


def test_has_valid_range_disabled_always_ok(qapp):
    panel = DurationPanel()
    panel.cb_custom_duration.setChecked(False)
    panel.le_start.setText("abc")
    panel.le_end.setText("xyz")
    assert panel.has_valid_range() is True


def test_has_valid_range_rejects_garbage(qapp):
    panel = DurationPanel()
    panel.cb_custom_duration.setChecked(True)
    panel.le_start.setText("abc")
    panel.le_end.setText("1:30")
    assert panel.has_valid_range() is False


def test_has_valid_range_accepts_times(qapp):
    panel = DurationPanel()
    panel.cb_custom_duration.setChecked(True)
    panel.le_start.setText("0:00")
    panel.le_end.setText("1:30")
    assert panel.has_valid_range() is True
    panel.le_end.setText("inf")
    assert panel.has_valid_range() is True


def test_has_valid_range_rejects_start_ge_end(qapp):
    panel = DurationPanel()
    panel.cb_custom_duration.setChecked(True)
    panel.le_start.setText("2:00")
    panel.le_end.setText("1:00")
    assert panel.has_valid_range() is False
    panel.le_start.setText("1:00")
    panel.le_end.setText("1:00")
    assert panel.has_valid_range() is False


def test_download_section_empty_when_invalid(qapp):
    panel = DurationPanel()
    panel.cb_custom_duration.setChecked(True)
    panel.le_start.setText("abc")
    panel.le_end.setText("1:30")
    assert panel.download_section() == ""
