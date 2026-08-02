from yt_dlp_gui.models.subtitle_spec import SubtitleSpec


def test_none_is_disabled():
    spec = SubtitleSpec.none()
    assert spec.mode == "none"
    assert not spec.enabled


def test_lang_mode_enabled():
    spec = SubtitleSpec(mode="lang", lang="es")
    assert spec.enabled


def test_round_trip_to_from_dict():
    spec = SubtitleSpec(mode="all_tracks", langs=["en", "es"])
    restored = SubtitleSpec.from_dict(spec.to_dict())
    assert restored == spec
