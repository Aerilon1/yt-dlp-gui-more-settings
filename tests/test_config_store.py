import pytest

from yt_dlp_gui.services import config_store


def test_seed_default_config_has_no_personal_data(tmp_path, monkeypatch):
    from yt_dlp_gui.services import paths

    monkeypatch.setattr(paths, "default_config_resource_path", lambda: tmp_path / "does-not-exist.toml")
    dest = tmp_path / "config.toml"
    config_store.seed_default_config(dest)
    config = config_store.load_config(dest)
    assert config.path == ""
    assert config.cookies_file == ""
    assert "mkv" in config.presets


def test_load_config_seeds_when_missing(tmp_path, monkeypatch):
    from yt_dlp_gui.services import paths

    monkeypatch.setattr(paths, "default_config_resource_path", lambda: tmp_path / "does-not-exist.toml")
    cfg_path = tmp_path / "sub" / "config.toml"
    config = config_store.load_config(cfg_path)
    assert cfg_path.is_file()
    assert config.retry_count == 2


def test_save_and_reload_round_trip(tmp_path):
    cfg_path = tmp_path / "config.toml"
    config = config_store.AppConfig(path="D:/videos", retry_count=5, max_concurrent_downloads=7)
    config_store.save_config(config, cfg_path)
    reloaded = config_store.load_config(cfg_path)
    assert reloaded.path == "D:/videos"
    assert reloaded.retry_count == 5
    assert reloaded.max_concurrent_downloads == 7


def test_malformed_toml_raises_config_error(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("this is not [ valid toml", encoding="utf-8")
    with pytest.raises(config_store.ConfigError):
        config_store.load_config(cfg_path)


def test_missing_preset_keys_fall_back_to_defaults(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[general]\npath = ""\n[presets]\ncustom = "-f best"\n', encoding="utf-8")
    config = config_store.load_config(cfg_path)
    assert "custom" in config.presets
    assert "mkv" in config.presets  # default presets still merged in


def test_invalid_integer_falls_back_to_default(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text('[general]\nretry_count = "not-a-number"\n', encoding="utf-8")
    config = config_store.load_config(cfg_path)
    assert config.retry_count == 2
