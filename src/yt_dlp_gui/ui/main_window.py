from __future__ import annotations

import json
import logging

from PySide6 import QtCore, QtGui, QtWidgets

from ..models.download_item import DownloadItem
from ..models.format_spec import FormatSpec
from ..models.playlist_entry import PlaylistEntry
from ..models.subtitle_spec import SubtitleSpec
from ..services import config_store, paths, probe_service, yt_dlp_args
from ..services.config_store import AppConfig
from ..services.download_engine import DownloadManager
from ..services.history_store import HistoryStore
from ..services.self_update_service import SelfUpdateService
from . import icons
from .widgets.cookies_panel import CookiesPanel
from .widgets.duration_panel import DurationPanel
from .widgets.format_options_panel import FormatOptionsPanel
from .widgets.history_panel import HistoryPanel
from .widgets.playlist_dialog import PlaylistDialog
from .widgets.queue_view import QueueView
from .widgets.settings_dialog import SettingsDialog
from .widgets.subtitle_panel import SubtitlePanel
from .widgets.url_input_panel import UrlInputPanel

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.setWindowTitle("yt-dlp-gui")
        self.resize(860, 640)
        icon_path = paths.icon_path()
        if icon_path.is_file():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))

        self.history_store = HistoryStore(paths.history_db_path())
        self.download_manager = DownloadManager(self.config, self)
        self.download_manager.item_added.connect(self._on_item_added)
        self.download_manager.item_updated.connect(self._on_item_updated)
        self.download_manager.item_removed.connect(self._on_item_removed)
        self.download_manager.item_finished.connect(self._on_item_finished)

        self._update_service = SelfUpdateService(self)
        self._update_service.finished_with_message.connect(self._on_update_finished)

        self._formats_thread: probe_service.ProbeThread | None = None
        self._dump_request_id = 0
        self._last_playlist_entries: list[PlaylistEntry] = []
        self._last_playlist_title = ""

        self._build_ui()
        self._wire_signals()
        self._load_settings_into_ui()
        QtCore.QTimer.singleShot(0, self._apply_toolbar_icons)

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)

        self.tabs = QtWidgets.QTabWidget()
        outer.addWidget(self.tabs, 1)

        downloads_tab = QtWidgets.QWidget()
        dl_layout = QtWidgets.QVBoxLayout(downloads_tab)

        self.params_group = QtWidgets.QGroupBox("Parameters")
        params_layout = QtWidgets.QVBoxLayout(self.params_group)

        self.url_panel = UrlInputPanel()
        params_layout.addWidget(self.url_panel)

        self.format_panel = FormatOptionsPanel(self.config.presets)
        params_layout.addWidget(self.format_panel)

        self.subtitle_panel = SubtitlePanel(lambda: self.config)
        params_layout.addWidget(self.subtitle_panel)

        self.duration_panel = DurationPanel()
        params_layout.addWidget(self.duration_panel)

        self.cookies_panel = CookiesPanel()
        params_layout.addWidget(self.cookies_panel)

        dl_layout.addWidget(self.params_group)

        queue_group = QtWidgets.QGroupBox("Downloads")
        queue_layout = QtWidgets.QVBoxLayout(queue_group)
        self.queue_view = QueueView()
        queue_layout.addWidget(self.queue_view)
        dl_layout.addWidget(queue_group, 1)

        button_row = QtWidgets.QHBoxLayout()
        self.pb_update = QtWidgets.QPushButton("Update")
        self.pb_update.setToolTip(
            "Run yt-dlp's built-in updater (same as yt-dlp -U in a terminal).\n"
            "Uses the yt-dlp executable from your PATH."
        )
        self.pb_settings = QtWidgets.QPushButton("Settings")
        self.pb_clear = QtWidgets.QPushButton("Clear")
        self.pb_download = QtWidgets.QPushButton("Download")
        button_row.addWidget(self.pb_update)
        button_row.addWidget(self.pb_settings)
        button_row.addStretch(1)
        button_row.addWidget(self.pb_clear)
        button_row.addWidget(self.pb_download)
        dl_layout.addLayout(button_row)

        self.tabs.addTab(downloads_tab, "Downloads")

        self.history_panel = HistoryPanel(self.history_store)
        self.tabs.addTab(self.history_panel, "History")

        self.setStatusBar(QtWidgets.QStatusBar())

    def _wire_signals(self) -> None:
        self.url_panel.add_clicked.connect(self._on_add_clicked)
        self.url_panel.debounced_url_changed.connect(self._on_debounced_url_change)
        self.url_panel.path_changed.connect(self._persist_general_preferences)
        self.url_panel.playlist_clicked.connect(self._on_playlist_button_clicked)

        self.subtitle_panel.scan_clicked.connect(self._on_scan_subs_clicked)
        self.subtitle_panel.status_message.connect(self._show_status)
        self.subtitle_panel.changed.connect(self._sync_subtitle_lock)
        self.subtitle_panel.video_info_scanned.connect(self._on_video_info_scanned)

        self.cookies_panel.changed.connect(self._persist_general_preferences)

        self.pb_update.clicked.connect(self._on_update_clicked)
        self.pb_settings.clicked.connect(self._on_settings_clicked)
        self.pb_clear.clicked.connect(self._on_clear_clicked)
        self.pb_download.clicked.connect(self._on_download_clicked)

        self.queue_view.retry_requested.connect(self.download_manager.retry)
        self.queue_view.cancel_requested.connect(self.download_manager.cancel)
        self.queue_view.remove_requested.connect(self.download_manager.remove)
        self.queue_view.status_message.connect(self._show_status)

        self.history_panel.redownload_requested.connect(self._on_redownload_requested)

    def _apply_toolbar_icons(self) -> None:
        """Load qtawesome after the first event-loop tick so startup isn't blocked on font I/O."""
        try:
            self.pb_update.setIcon(icons.icon("mdi6.update"))
        except Exception:
            self.pb_update.setIcon(icons.icon("mdi6.refresh"))
        self.pb_clear.setIcon(icons.icon("mdi6.trash-can-outline"))
        self.pb_download.setIcon(icons.icon("mdi6.download"))
        self.pb_settings.setIcon(icons.icon("mdi6.cog-outline"))

    # ------------------------------------------------------------ settings

    def _load_settings_into_ui(self) -> None:
        self.url_panel.set_destination(self.config.path)
        self.format_panel.set_current_preset_index(self.config.current_preset)
        self.format_panel.set_use_saved_preset(self.config.use_saved_preset)
        self.cookies_panel.set_path(yt_dlp_args.default_cookies_file_display(self.config))
        self._refresh_quality_ui_for_site()

    def _show_status(self, text: str, duration_ms: int = 4000) -> None:
        self.statusBar().showMessage(text, duration_ms)

    def _persist_general_preferences(self) -> None:
        self.config.path = self.url_panel.destination()
        self.config.cookies_file = self.cookies_panel.path()
        try:
            config_store.save_config(self.config)
        except OSError as e:
            logger.warning("Could not save settings: %s", e)

    # --------------------------------------------------------------- probe

    def _on_debounced_url_change(self) -> None:
        self._refresh_quality_ui_for_site()
        self._start_format_probe_for_first_url()

    def _refresh_quality_ui_for_site(self) -> None:
        first = self.url_panel.first_url()
        if not first:
            self.params_group.setTitle("Parameters")
            return
        if yt_dlp_args.is_youtube_url(first):
            self.params_group.setTitle("Parameters — YouTube")
        else:
            self.params_group.setTitle("Parameters — other site")

    def _start_format_probe_for_first_url(self) -> None:
        probe_service.abort_thread(self._formats_thread)
        first = self.url_panel.first_url()
        self._last_playlist_entries = []
        self._last_playlist_title = ""
        self.url_panel.set_playlist_detected(False)
        self._dump_request_id += 1
        if not first:
            self.format_panel.set_video_info("", None)
            return
        rid = self._dump_request_id
        thread = probe_service.ProbeThread(first, self.config, rid, flat_playlist=True, parent=self)
        self._formats_thread = thread
        thread.result_ready.connect(self._on_format_probe_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_format_probe_finished(self, request_id: int, probed_url: str, json_str: str | None) -> None:
        if request_id != self._dump_request_id:
            return
        first = self.url_panel.first_url()
        if first != (probed_url or "").strip():
            return
        info = None
        if json_str:
            try:
                info = json.loads(json_str)
            except json.JSONDecodeError:
                info = None
        if info and probe_service.is_playlist_info(info):
            entries = probe_service.playlist_entries_from_info(info)
            self._last_playlist_entries = entries
            self._last_playlist_title = info.get("title") or ""
            self.url_panel.set_playlist_detected(True, len(entries))
            self.format_panel.set_video_info(probed_url, None)
        else:
            self.format_panel.set_video_info(probed_url, info)

    def _on_video_info_scanned(self, url: str, info: dict) -> None:
        if url == self.url_panel.first_url() and not probe_service.is_playlist_info(info):
            self.format_panel.set_video_info(url, info)

    def _on_scan_subs_clicked(self) -> None:
        if self._last_playlist_entries:
            QtWidgets.QMessageBox.information(
                self,
                "Application Message",
                "This URL looks like a playlist. Pick videos via Playlist first, "
                "or paste a single video URL before scanning subtitles.",
            )
            self._show_status("Subtitle scan skipped — choose playlist videos or a single URL.", 6000)
            return
        self.subtitle_panel.start_scan(self.url_panel.first_url())

    def _sync_subtitle_lock(self) -> None:
        self.format_panel.lock_for_subtitles(self.subtitle_panel.is_enabled_mode())

    # ---------------------------------------------------------------- add

    def _on_add_clicked(self) -> None:
        self._add_from_form()

    def _add_from_form(self) -> bool:
        urls = self.url_panel.urls()
        destination = self.url_panel.destination()
        missing = []
        if not urls:
            missing.append("Video URL")
        if not destination:
            missing.append("Save to")
        if missing:
            QtWidgets.QMessageBox.information(
                self,
                "Application Message",
                f"Required field{'s' if len(missing) > 1 else ''} ({', '.join(missing)}) missing.",
            )
            return False

        if self.duration_panel.is_enabled() and not self.duration_panel.has_valid_range():
            QtWidgets.QMessageBox.information(
                self,
                "Application Message",
                "Custom duration is enabled: enter valid start and end times "
                "(e.g. 0:00 and 1:30, [[HH:]MM:]SS, or inf for end of video). "
                "Start must be before end.",
            )
            return False

        if self.format_panel.use_saved_preset() and self.format_panel.selected_preset_key() not in self.config.presets:
            QtWidgets.QMessageBox.information(self, "Application Message", "Choose a valid saved preset.")
            return False

        self._persist_general_preferences()
        download_section = self.duration_panel.download_section()

        for url in urls:
            self._enqueue_url(url, destination, download_section)

        self.url_panel.clear_urls()
        return True

    def _enqueue_url(self, url: str, destination: str, download_section: str, title: str = "") -> None:
        format_spec = self.format_panel.build_format_spec(url, self.config.presets)
        if format_spec is None:
            return
        subtitle_spec = self.subtitle_panel.build_subtitle_spec(url)
        kwargs = dict(
            url=url,
            destination_dir=destination,
            format_spec=format_spec,
            subtitle_spec=subtitle_spec,
            download_section=download_section or None,
        )
        if title:
            kwargs["title"] = title
            kwargs["source"] = "playlist"
        item = DownloadItem(**kwargs)
        self.download_manager.enqueue(item)
        logger.info("Queued download (%s) added %s", item.id, url)

    def _on_download_clicked(self) -> None:
        if self.url_panel.urls():
            if not self._add_from_form():
                return
        if not self.download_manager.items:
            QtWidgets.QMessageBox.information(
                self, "Application Message", "Unable to download because there are no links in the list."
            )

    def _on_clear_clicked(self) -> None:
        if self.download_manager.active_workers:
            QtWidgets.QMessageBox.critical(
                self,
                "Application Message",
                "Unable to clear list because there are active downloads in progress.\n"
                "Remove a download by right clicking on it and selecting delete.",
            )
            return
        for item_id in list(self.download_manager.items.keys()):
            self.download_manager.remove(item_id)

    # ------------------------------------------------------------- queue UI

    def _on_item_added(self, item: DownloadItem) -> None:
        self.queue_view.model_.add_item(item)

    def _on_item_updated(self, item_id: int, fields: dict) -> None:
        self.queue_view.model_.update_item(item_id, fields)

    def _on_item_removed(self, item_id: int) -> None:
        self.queue_view.model_.remove_item(item_id)

    def _on_item_finished(self, item: DownloadItem) -> None:
        self.history_store.record_finished_item(item)
        self.history_panel.refresh()

    # ------------------------------------------------------------ playlist

    def _on_playlist_button_clicked(self) -> None:
        if not self._last_playlist_entries:
            return
        dialog = PlaylistDialog(self._last_playlist_entries, self._last_playlist_title, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_entries()
        if not selected:
            return
        destination = self.url_panel.destination()
        if not destination:
            QtWidgets.QMessageBox.information(self, "Application Message", "Choose a Save to folder first.")
            return
        if self.duration_panel.is_enabled() and not self.duration_panel.has_valid_range():
            QtWidgets.QMessageBox.information(
                self,
                "Application Message",
                "Custom duration is enabled: enter valid start and end times "
                "(e.g. 0:00 and 1:30, [[HH:]MM:]SS, or inf for end of video). "
                "Start must be before end.",
            )
            return
        self._persist_general_preferences()
        download_section = self.duration_panel.download_section()
        for entry in selected:
            self._enqueue_url(entry.url, destination, download_section, title=entry.title)

        first_line_url = self.url_panel.first_url()
        remaining = [u for u in self.url_panel.urls() if u != first_line_url]
        self.url_panel.set_urls(remaining)
        self.url_panel.set_playlist_detected(False)
        self._last_playlist_entries = []

    # --------------------------------------------------------------- update

    def _on_update_clicked(self) -> None:
        if self._update_service.is_running():
            self._show_status("yt-dlp is already running an update check.", 4000)
            return
        self.pb_update.setEnabled(False)
        self._show_status("Checking for yt-dlp updates…", 0)
        self._update_service.start()

    def _on_update_finished(self, message: str, duration_ms: int) -> None:
        self.pb_update.setEnabled(True)
        self._show_status(message, duration_ms)

    def _on_settings_clicked(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            dialog.apply_to(self.config)
            self.download_manager.set_max_concurrent(self.config.max_concurrent_downloads)
            try:
                config_store.save_config(self.config)
            except OSError as e:
                logger.warning("Could not save settings: %s", e)

    def _on_redownload_requested(self, entry) -> None:
        try:
            format_data = json.loads(entry.format_argv_json)
            subtitle_data = json.loads(entry.subtitle_spec_json)
        except json.JSONDecodeError:
            self._show_status("Could not re-download: stored settings are corrupt.", 6000)
            return
        item = DownloadItem(
            url=entry.url,
            destination_dir=entry.destination_dir or self.url_panel.destination(),
            format_spec=FormatSpec.from_dict(format_data),
            subtitle_spec=SubtitleSpec.from_dict(subtitle_data),
            download_section=entry.download_section or None,
        )
        self.download_manager.enqueue(item)
        self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------- shutdown

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self._update_service.shutdown()
        probe_service.abort_thread(self._formats_thread, wait_ms=4000)
        self.subtitle_panel.abort_pending_scan(wait_ms=4000)
        self.download_manager.shutdown()

        self.config.current_preset = self.format_panel.current_preset_index()
        self.config.use_saved_preset = self.format_panel.use_saved_preset()
        self.config.path = self.url_panel.destination()
        self.config.cookies_file = self.cookies_panel.path()
        try:
            config_store.save_config(self.config)
        except OSError as e:
            logger.warning("Could not save config: %s", e)
            self._show_status(
                f"Settings were not saved ({e}). If the app is in a protected folder, "
                "move it or run with permission to write your config file.",
                10000,
            )
        self.history_store.close()
        event.accept()
