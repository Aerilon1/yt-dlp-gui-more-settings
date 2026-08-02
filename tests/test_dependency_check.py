from yt_dlp_gui.services import dependency_check


def test_ok_when_nothing_missing(monkeypatch):
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(dependency_check.yt_dlp_args, "yt_dlp_js_runtime_argv", lambda: ["--js-runtimes", "deno:x"])
    status = dependency_check.check_dependencies()
    assert status.ok
    assert status.missing_required == []
    assert status.js_runtime_available


def test_not_ok_when_required_tool_missing(monkeypatch):
    def fake_which(name):
        return None if name == "ffmpeg" else f"/usr/bin/{name}"

    monkeypatch.setattr(dependency_check.shutil, "which", fake_which)
    monkeypatch.setattr(dependency_check.yt_dlp_args, "yt_dlp_js_runtime_argv", lambda: [])
    status = dependency_check.check_dependencies()
    assert not status.ok
    assert status.missing_required == ["ffmpeg"]


def test_js_runtime_missing_is_not_a_hard_failure(monkeypatch):
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(dependency_check.yt_dlp_args, "yt_dlp_js_runtime_argv", lambda: [])
    status = dependency_check.check_dependencies()
    assert status.ok  # still ok -- JS runtime is a soft requirement
    assert not status.js_runtime_available


def test_all_required_tools_missing(monkeypatch):
    monkeypatch.setattr(dependency_check.shutil, "which", lambda name: None)
    monkeypatch.setattr(dependency_check.yt_dlp_args, "yt_dlp_js_runtime_argv", lambda: [])
    status = dependency_check.check_dependencies()
    assert not status.ok
    assert set(status.missing_required) == set(dependency_check.REQUIRED_TOOLS)
