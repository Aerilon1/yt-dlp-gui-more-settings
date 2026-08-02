"""
Tests DownloadManager's concurrency dispatch logic in isolation, using a fake worker in
place of DownloadWorker (which needs a real yt-dlp subprocess) -- this is what fixes the
pre-rewrite bug where every queued item started its subprocess simultaneously with no cap.
"""
from PySide6 import QtCore, QtWidgets

from yt_dlp_gui.models.download_item import DownloadItem, DownloadState
from yt_dlp_gui.models.format_spec import FormatSpec
from yt_dlp_gui.services import config_store, download_engine

if QtWidgets.QApplication.instance() is None:
    _app = QtWidgets.QApplication([])


class FakeWorker(QtCore.QObject):
    progress = QtCore.Signal(int, dict)
    finished = QtCore.Signal(int)

    def __init__(self, item, config, parent=None):
        super().__init__(parent)
        self.item_id = item.id
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        self.finished.emit(self.item_id)

    def wait(self, _ms):
        return True

    def deleteLater(self):
        pass


def _make_item(i: int) -> DownloadItem:
    return DownloadItem(
        url=f"https://example.com/{i}",
        destination_dir="C:/downloads",
        format_spec=FormatSpec(mode="manual", resolved_argv=["-f", "best"]),
    )


def _manager(max_concurrent: int, monkeypatch) -> download_engine.DownloadManager:
    monkeypatch.setattr(download_engine, "DownloadWorker", FakeWorker)
    config = config_store.AppConfig(max_concurrent_downloads=max_concurrent)
    return download_engine.DownloadManager(config)


def test_enqueue_beyond_limit_waits_in_pending(monkeypatch):
    mgr = _manager(2, monkeypatch)
    for i in range(4):
        mgr.enqueue(_make_item(i))

    assert len(mgr.active_workers) == 2
    assert len(mgr.pending_ids) == 2
    for w in mgr.active_workers.values():
        assert w.started


def test_finishing_one_worker_starts_the_next_pending_item(monkeypatch):
    mgr = _manager(2, monkeypatch)
    items = [_make_item(i) for i in range(3)]
    for item in items:
        mgr.enqueue(item)

    assert len(mgr.active_workers) == 2
    assert len(mgr.pending_ids) == 1

    first_active_id = next(iter(mgr.active_workers))
    worker = mgr.active_workers[first_active_id]
    worker.finished.emit(first_active_id)

    assert len(mgr.active_workers) == 2
    assert len(mgr.pending_ids) == 0
    assert items[2].id in mgr.active_workers


def test_cancel_pending_item_never_starts_it(monkeypatch):
    mgr = _manager(1, monkeypatch)
    items = [_make_item(i) for i in range(2)]
    for item in items:
        mgr.enqueue(item)

    assert items[1].id in mgr.pending_ids
    mgr.cancel(items[1].id)
    assert items[1].id not in mgr.pending_ids
    assert items[1].state == DownloadState.CANCELLED


def test_cancel_active_item_calls_stop(monkeypatch):
    mgr = _manager(1, monkeypatch)
    item = _make_item(0)
    mgr.enqueue(item)
    worker = mgr.active_workers[item.id]

    mgr.cancel(item.id)
    assert worker.stopped


def test_set_max_concurrent_dispatches_more_immediately(monkeypatch):
    mgr = _manager(1, monkeypatch)
    items = [_make_item(i) for i in range(3)]
    for item in items:
        mgr.enqueue(item)

    assert len(mgr.active_workers) == 1
    assert len(mgr.pending_ids) == 2

    mgr.set_max_concurrent(3)

    assert len(mgr.active_workers) == 3
    assert len(mgr.pending_ids) == 0


def test_retry_does_not_reuse_old_settings_from_other_items(monkeypatch):
    """Retrying item A must never pick up settings from a later scan/edit of item B --
    that cross-item state bleed was the root cause of the pre-rewrite subtitle bug."""
    mgr = _manager(2, monkeypatch)
    item_a = _make_item(0)
    item_a.subtitle_spec.mode = "all_tracks"
    item_a.subtitle_spec.langs = ["en", "es"]
    mgr.enqueue(item_a)

    worker_a = mgr.active_workers[item_a.id]
    item_a.state = DownloadState.ERROR
    worker_a.finished.emit(item_a.id)

    item_b = _make_item(1)
    item_b.subtitle_spec.mode = "all_tracks"
    item_b.subtitle_spec.langs = ["en"]
    mgr.enqueue(item_b)

    mgr.retry(item_a.id)

    assert item_a.subtitle_spec.langs == ["en", "es"]


def test_subtitle_build_command_omits_ignore_errors(tmp_path, monkeypatch):
    """Subtitle jobs must not blanket --ignore-errors (false Finished on hard failures)."""
    from yt_dlp_gui.models.subtitle_spec import SubtitleSpec

    monkeypatch.setattr(download_engine.tempfile, "mkdtemp", lambda prefix="": str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir(exist_ok=True)

    item = DownloadItem(
        url="https://example.com/v",
        destination_dir=str(tmp_path),
        format_spec=FormatSpec(mode="manual", resolved_argv=["-f", "best", "--merge-output-format", "mkv"]),
        subtitle_spec=SubtitleSpec(mode="lang", lang="en"),
    )
    config = config_store.AppConfig(path=str(tmp_path), retry_count=0)
    worker = download_engine.DownloadWorker(item, config)
    assert "--ignore-errors" not in worker.command
    assert "-i" not in worker.command
    assert "--sleep-subtitles" in worker.command
    assert "--embed-subs" in worker.command


def test_subtitle_all_modes_skip_when_no_langs(tmp_path, monkeypatch):
    """all_tracks/all with empty langs must not fall back to --sub-langs en."""
    from yt_dlp_gui.models.subtitle_spec import SubtitleSpec

    monkeypatch.setattr(download_engine.tempfile, "mkdtemp", lambda prefix="": str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir(exist_ok=True)

    item = DownloadItem(
        url="https://example.com/v",
        destination_dir=str(tmp_path),
        format_spec=FormatSpec(mode="manual", resolved_argv=["-f", "best", "--merge-output-format", "mp4"]),
        subtitle_spec=SubtitleSpec(mode="all_tracks", langs=[]),
    )
    config = config_store.AppConfig(path=str(tmp_path), retry_count=0)
    worker = download_engine.DownloadWorker(item, config)
    assert "--embed-subs" not in worker.command
    assert "--sub-langs" not in worker.command
    assert "--sleep-subtitles" not in worker.command
