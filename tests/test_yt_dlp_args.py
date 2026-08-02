from yt_dlp_gui.services import yt_dlp_args


class _Cfg:
    def __init__(self, cookies_file=""):
        self.cookies_file = cookies_file


def test_build_manual_format_argv_audio():
    argv = yt_dlp_gui_build_audio = yt_dlp_args.build_manual_format_argv("audio", "mp3", "best", None, "https://example.com/v")
    assert argv == ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "0"]


def test_build_manual_format_argv_audio_wav():
    argv = yt_dlp_args.build_manual_format_argv("audio", "wav", "best", None, "")
    assert argv == ["--extract-audio", "--audio-format", "wav", "--audio-quality", "0"]


def test_build_manual_format_argv_video_mp4_youtube_no_height():
    argv = yt_dlp_args.build_manual_format_argv("video", "mp4", "best", None, "https://www.youtube.com/watch?v=x")
    assert argv == ["-f", "bv*[vcodec^=avc]+ba[ext=m4a]/b", "--merge-output-format", "mp4"]


def test_build_manual_format_argv_video_mp4_youtube_with_height():
    argv = yt_dlp_args.build_manual_format_argv("video", "mp4", "height_cap", 1080, "https://youtu.be/x")
    assert argv[0] == "-f"
    assert "[height<=1080]" in argv[1]
    assert "vcodec^=avc" in argv[1]
    assert argv[-2:] == ["--merge-output-format", "mp4"]


def test_build_manual_format_argv_video_mp4_other_site():
    argv = yt_dlp_args.build_manual_format_argv("video", "mp4", "best", None, "https://vimeo.com/12345")
    assert argv == ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]


def test_build_manual_format_argv_video_mkv_with_height():
    argv = yt_dlp_args.build_manual_format_argv("video", "mkv", "height_cap", 720, "https://example.com/v")
    assert argv == ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best", "--merge-output-format", "mkv"]


def test_build_manual_format_argv_empty_container_defaults_to_mp4():
    argv = yt_dlp_args.build_manual_format_argv("video", "", "best", None, "https://example.com/v")
    assert argv == ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]


def test_build_manual_format_argv_unknown_container_merge_falls_back_to_mp4():
    argv = yt_dlp_args.build_manual_format_argv("video", "avi", "best", None, "https://example.com/v")
    assert argv[-2:] == ["--merge-output-format", "mp4"]


def test_is_youtube_url_variants():
    assert yt_dlp_args.is_youtube_url("https://www.youtube.com/watch?v=x")
    assert yt_dlp_args.is_youtube_url("https://youtu.be/x")
    assert yt_dlp_args.is_youtube_url("youtube.com/watch?v=x")
    assert yt_dlp_args.is_youtube_url("www.youtube.com/watch?v=x")
    assert not yt_dlp_args.is_youtube_url("https://vimeo.com/12345")
    assert not yt_dlp_args.is_youtube_url("")


def test_video_heights_from_info_dedup_and_sorted():
    info = {
        "formats": [
            {"height": 1080.0, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "vp9"},
            {"height": 720, "vcodec": "avc1"},
            {"height": None, "vcodec": "avc1"},
            {"height": 480, "vcodec": "none"},
        ]
    }
    assert yt_dlp_args.video_heights_from_info(info) == [1080, 720]


def test_video_heights_from_info_none():
    assert yt_dlp_args.video_heights_from_info(None) == []
    assert yt_dlp_args.video_heights_from_info({}) == []


def test_resolve_preset_argv_mp4_on_youtube():
    presets = {"mp4": "-f bv*[vcodec^=avc]+ba[ext=m4a]/b"}
    argv = yt_dlp_args.resolve_preset_argv("mp4", "https://www.youtube.com/watch?v=x", presets)
    assert argv == ["-f", "bv*[vcodec^=avc]+ba[ext=m4a]/b"]


def test_resolve_preset_argv_mp4_on_other_site_falls_back():
    presets = {"mp4": "-f bv*[vcodec^=avc]+ba[ext=m4a]/b"}
    argv = yt_dlp_args.resolve_preset_argv("mp4", "https://vimeo.com/1", presets)
    assert argv == ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]


def test_resolve_preset_argv_unknown_preset():
    assert yt_dlp_args.resolve_preset_argv("nope", "https://example.com", {}) == []


def test_cookie_args_missing_file_falls_through(tmp_path, monkeypatch):
    from yt_dlp_gui.services import paths

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    cfg = _Cfg(cookies_file="does-not-exist.txt")
    assert yt_dlp_args.cookie_args(cfg) == []


def test_cookie_args_auto_detects_cookies_txt(tmp_path, monkeypatch):
    from yt_dlp_gui.services import paths

    monkeypatch.setattr(paths, "user_data_dir", lambda: tmp_path)
    (tmp_path / "cookies.txt").write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    cfg = _Cfg(cookies_file="")
    args = yt_dlp_args.cookie_args(cfg)
    assert args[0] == "--cookies"
    assert args[1].endswith("cookies.txt")
