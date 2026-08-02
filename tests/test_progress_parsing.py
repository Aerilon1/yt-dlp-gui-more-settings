from yt_dlp_gui.services.download_engine import (
    _argv_has_absolute_output_path,
    _argv_has_compat_no_direct_merge,
    _argv_requests_extract_audio,
    _hard_failure_despite_zero_exit,
    _parse_ytdlp_download_bracket_line,
    _short_yt_dlp_failure_status,
)


def test_parse_bracket_line_percent_speed_eta():
    result = _parse_ytdlp_download_bracket_line("[download]  42.0% of 10.00MiB at 1.50MiB/s ETA 00:05")
    assert result["progress"] == "42%"
    assert result["speed"] == "1.50MiB/s"
    assert result["eta"] == "00:05"


def test_parse_bracket_line_destination_is_ignored():
    assert _parse_ytdlp_download_bracket_line("[download] Destination: video.mp4") is None


def test_parse_bracket_line_fragment_progress():
    result = _parse_ytdlp_download_bracket_line("[download] Downloading video 3 of 12")
    assert result["progress"] == "25%"


def test_parse_bracket_line_non_download_line_is_none():
    assert _parse_ytdlp_download_bracket_line("[youtube] Extracting URL") is None


def test_short_failure_status_js_runtime():
    assert "JS runtime" in _short_yt_dlp_failure_status("ERROR: [youtube] n challenge solving failed")


def test_short_failure_status_bot_check():
    assert "bot check" in _short_yt_dlp_failure_status("Sign in to confirm you're not a bot")


def test_short_failure_status_invalid_url():
    assert "Invalid URL" in _short_yt_dlp_failure_status("ERROR: 'not-a-url' is not a valid URL")


def test_short_failure_status_generic_error_line():
    result = _short_yt_dlp_failure_status("some noise\nERROR: Unable to download webpage\nmore noise")
    assert result == "ERROR: Unable to download webpage"


def test_short_failure_status_empty_output():
    assert _short_yt_dlp_failure_status("") == "ERROR"


def test_hard_failure_despite_zero_exit_postprocess():
    out = "[download] 100%\nERROR: Postprocessing: Error opening output files\n"
    assert _hard_failure_despite_zero_exit(out)


def test_hard_failure_despite_zero_exit_ignores_soft_subtitle_errors():
    out = (
        "[download] 100%\n"
        "ERROR: Unable to download video subtitles for 'es': HTTP Error 404: Not Found\n"
        "[EmbedSubtitle] Embedding subtitles\n"
    )
    assert not _hard_failure_despite_zero_exit(out)


def test_hard_failure_despite_zero_exit_clean_success():
    assert not _hard_failure_despite_zero_exit("[download] 100%\n[Merger] Merging formats into mkv\n")


def test_hard_failure_despite_zero_exit_embed_subtitle_failure():
    out = "[download] 100%\nERROR: Embedding of subtitles failed: ffmpeg returned non-zero\n"
    assert _hard_failure_despite_zero_exit(out)


def test_argv_requests_extract_audio():
    assert _argv_requests_extract_audio(["-x", "--audio-format", "mp3"])
    assert not _argv_requests_extract_audio(["-f", "best"])


def test_argv_has_compat_no_direct_merge():
    assert _argv_has_compat_no_direct_merge(["--compat-options", "no-direct-merge,other"])
    assert not _argv_has_compat_no_direct_merge(["--compat-options", "other"])
    assert not _argv_has_compat_no_direct_merge(["-f", "best"])


def test_argv_has_absolute_output_path_windows_drive(tmp_path):
    # A literal absolute path with no yt-dlp %(...) template is what this detects.
    argv = ["-o", str(tmp_path / "video.mp4")]
    assert _argv_has_absolute_output_path(argv)


def test_argv_has_absolute_output_path_template_only():
    assert not _argv_has_absolute_output_path(["-o", "%(title)s.%(ext)s"])


def test_argv_has_absolute_output_path_none():
    assert not _argv_has_absolute_output_path(["-f", "best"])
