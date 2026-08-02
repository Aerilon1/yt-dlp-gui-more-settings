from yt_dlp_gui.services.probe_service import is_playlist_info, playlist_entries_from_info


def test_is_playlist_info_true_for_entries():
    assert is_playlist_info({"_type": "playlist", "entries": [{"id": "a"}]})


def test_is_playlist_info_false_for_single_video():
    assert not is_playlist_info({"id": "abc123", "title": "A video"})


def test_is_playlist_info_false_for_none():
    assert not is_playlist_info(None)


def test_playlist_entries_from_info_basic():
    info = {
        "title": "My Playlist",
        "entries": [
            {"id": "a1", "title": "Video One", "webpage_url": "https://example.com/a1", "duration": 90},
            {"id": "a2", "title": "Video Two", "url": "https://example.com/a2", "duration": 3725},
        ],
    }
    entries = playlist_entries_from_info(info)
    assert len(entries) == 2
    assert entries[0].index == 1
    assert entries[0].title == "Video One"
    assert entries[0].url == "https://example.com/a1"
    assert entries[0].duration_text == "1:30"
    assert entries[1].duration_text == "1:02:05"


def test_playlist_entries_from_info_skips_entries_with_no_identifier_at_all():
    info = {"entries": [{"title": "No URL or ID"}, {"id": "a2", "title": "Has ID", "url": "https://x/a2"}]}
    entries = playlist_entries_from_info(info)
    assert len(entries) == 1
    assert entries[0].title == "Has ID"


def test_playlist_entries_from_info_falls_back_to_id_when_no_url():
    info = {"entries": [{"id": "a1", "title": "Only ID"}]}
    entries = playlist_entries_from_info(info)
    assert len(entries) == 1
    assert entries[0].url == "a1"


def test_playlist_entries_from_info_empty():
    assert playlist_entries_from_info({}) == []
