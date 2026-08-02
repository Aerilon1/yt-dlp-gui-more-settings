from yt_dlp_gui.models.download_item import DownloadItem, DownloadState
from yt_dlp_gui.models.format_spec import FormatSpec
from yt_dlp_gui.services.history_store import HistoryStore


def _make_item(url="https://example.com/a", title="Video A", state=DownloadState.FINISHED, status_text="Finished"):
    item = DownloadItem(
        url=url,
        destination_dir="C:/downloads",
        format_spec=FormatSpec(mode="manual", resolved_argv=["-f", "best"]),
        title=title,
    )
    item.state = state
    item.status_text = status_text
    return item


def test_record_and_search_finished_item(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.record_finished_item(_make_item())
    results = store.search("")
    assert len(results) == 1
    assert results[0].title == "Video A"
    assert results[0].status == "Finished"
    store.close()


def test_record_skips_non_terminal_state(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.record_finished_item(_make_item(state=DownloadState.DOWNLOADING, status_text="Downloading"))
    assert store.search("") == []
    store.close()


def test_record_error_item(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.record_finished_item(_make_item(state=DownloadState.ERROR, status_text="ERROR: invalid URL"))
    results = store.search("")
    assert results[0].status == "ERROR"
    assert results[0].error_message == "ERROR: invalid URL"
    store.close()


def test_search_filters_by_title_or_url(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.record_finished_item(_make_item(url="https://example.com/a", title="Cats compilation"))
    store.record_finished_item(_make_item(url="https://example.com/b", title="Dogs compilation"))
    assert len(store.search("cats")) == 1
    assert len(store.search("compilation")) == 2
    assert len(store.search("nonexistent")) == 0
    store.close()


def test_delete_removes_entry(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")
    store.record_finished_item(_make_item())
    entry_id = store.search("")[0].id
    store.delete(entry_id)
    assert store.search("") == []
    store.close()


def test_persists_across_reopen(tmp_path):
    db_path = tmp_path / "history.sqlite3"
    store = HistoryStore(db_path)
    store.record_finished_item(_make_item())
    store.close()

    store2 = HistoryStore(db_path)
    assert len(store2.search("")) == 1
    store2.close()
