from yt_dlp_gui.models.format_spec import FormatSpec


def test_manual_label_best():
    spec = FormatSpec(mode="manual", file_type="video", container="mkv", quality_mode="best")
    assert spec.label() == "Manual: Best mkv"


def test_manual_label_height_cap_audio():
    spec = FormatSpec(mode="manual", file_type="audio", container="mp3", quality_mode="height_cap", max_height=720)
    assert spec.label() == "Manual: Best mp3 (audio)"


def test_manual_label_video_height_cap():
    spec = FormatSpec(mode="manual", file_type="video", container="mp4", quality_mode="height_cap", max_height=1080)
    assert spec.label() == "Manual: 1080p (max) mp4"


def test_preset_label_uses_preset_key():
    spec = FormatSpec(mode="preset", preset_key="mkv")
    assert spec.label() == "mkv"


def test_round_trip_to_from_dict():
    spec = FormatSpec(
        mode="manual",
        file_type="video",
        container="mp4",
        quality_mode="height_cap",
        max_height=720,
        resolved_argv=["-f", "bestvideo", "--merge-output-format", "mp4"],
    )
    restored = FormatSpec.from_dict(spec.to_dict())
    assert restored == spec
