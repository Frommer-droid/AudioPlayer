"""Frozen settings survive an admin-installed read-only program directory."""
from app.core import settings


def test_frozen_data_root_prefers_portable_and_falls_back(tmp_path, monkeypatch):
    portable = tmp_path / "portable"
    portable.mkdir()
    monkeypatch.setattr(settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(settings.sys, "executable", str(portable / "AudioPlayer.exe"))
    assert settings.data_root() == portable

    def denied(**kwargs):
        raise PermissionError("read-only installation")

    monkeypatch.setattr(settings.tempfile, "TemporaryFile", denied)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    assert settings.data_root() == tmp_path / "local-app-data" / "AudioPlayer"
    assert settings.data_root().is_dir()
