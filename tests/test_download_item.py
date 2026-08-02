from yt_dlp_gui.models.download_item import DownloadItem, DownloadState, next_item_id
from yt_dlp_gui.models.format_spec import FormatSpec
from yt_dlp_gui.models.subtitle_spec import SubtitleSpec


def _make_item(**overrides):
    kwargs = dict(
        url="https://example.com/video",
        destination_dir="C:/downloads",
        format_spec=FormatSpec(mode="manual", resolved_argv=["-f", "best"]),
    )
    kwargs.update(overrides)
    return DownloadItem(**kwargs)


def test_ids_are_unique_and_increasing():
    a = next_item_id()
    b = next_item_id()
    assert b > a


def test_default_title_falls_back_to_url():
    item = _make_item()
    assert item.title == item.url


def test_default_state_is_queued():
    item = _make_item()
    assert item.state == DownloadState.QUEUED
    assert item.status_text == "Queued"


def test_default_subtitle_spec_is_none():
    item = _make_item()
    assert item.subtitle_spec == SubtitleSpec.none()


def test_queue_label_delegates_to_format_spec():
    item = _make_item(format_spec=FormatSpec(mode="preset", preset_key="mp4"))
    assert item.queue_label() == "mp4"


def test_two_items_never_share_subtitle_spec_instance():
    """Two DownloadItems must never share the same SubtitleSpec object -- that was the
    root cause of the pre-rewrite cross-item subtitle contamination bug."""
    a = _make_item(subtitle_spec=SubtitleSpec(mode="all_tracks", langs=["en", "es"]))
    b = _make_item(subtitle_spec=SubtitleSpec(mode="all_tracks", langs=["en"]))
    assert a.subtitle_spec is not b.subtitle_spec
    b.subtitle_spec.langs.append("fr")
    assert a.subtitle_spec.langs == ["en", "es"]
