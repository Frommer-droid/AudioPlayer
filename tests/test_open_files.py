"""Открытие из главного окна выбирает трек, добавление сохраняет текущий."""
import wave

import pytest
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_runtime import wait_until


def make_tracks(tmp_path):
    paths = [tmp_path / f"{name}.wav" for name in ("previous", "chosen", "extra")]
    for path in paths:
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x10" * 64000)
    return paths


@pytest.mark.parametrize("already_added", [False, True])
def test_cover_left_click_switches_to_selected_file(qt_app, tmp_path, monkeypatch, already_added):
    previous, chosen, extra = make_tracks(tmp_path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths([previous, chosen] if already_added else [previous])
    window.show()
    try:
        window.play(0)
        monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames",
                            lambda *args: ([str(chosen), str(extra)], ""))
        QTest.mouseClick(window.cover, Qt.MouseButton.LeftButton)
        assert window.playlist.paths[window.playlist.current] == chosen
        assert window.player.media.source().toLocalFile() == str(chosen).replace("\\", "/")
        assert window.track_title.text() == chosen.stem
        assert window.table.currentRow() == window.playlist.current
        assert window.playlist.paths == [previous, chosen, extra]
        wait_until(lambda: window.player.media.position() > 0 and bool(window.wave.peaks))
        assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    finally:
        window.close()


def test_cancel_and_playlist_add_keep_current_track(qt_app, tmp_path, monkeypatch):
    previous, chosen, _extra = make_tracks(tmp_path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths([previous])
    window.show()
    try:
        window.play(0)
        source = window.player.media.source()
        monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames", lambda *args: ([], ""))
        QTest.mouseClick(window.cover, Qt.MouseButton.LeftButton)
        assert window.player.media.source() == source
        assert window.playlist.paths == [previous]
        monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames",
                            lambda *args: ([str(chosen)], ""))
        window._add_files()
        assert window.playlist.paths == [previous, chosen]
        assert window.playlist.current == 0
        assert window.player.media.source() == source
    finally:
        window.close()


@pytest.mark.parametrize("already_added", [False, True])
def test_external_open_starts_first_valid_track(qt_app, tmp_path, already_added):
    previous, chosen, extra = make_tracks(tmp_path)
    renamed = tmp_path / "Трек с пробелами.wav"
    chosen.rename(renamed)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths([previous, renamed] if already_added else [previous])
    try:
        window.open_paths([str(tmp_path / "missing.wav"), str(renamed), str(extra)])
        assert window.playlist.paths == [previous, renamed, extra]
        assert window.playlist.paths[window.playlist.current] == renamed
        wait_until(lambda: window.player.media.position() > 0)
        assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    finally:
        window.close()
    assert window.store.load()["last_directory"] == str(renamed.parent)


@pytest.mark.parametrize("play_selected", [False, True])
def test_last_directory_shared_by_dialogs_and_persists(qt_app, tmp_path, monkeypatch, play_selected):
    first = tmp_path / "Первая папка"
    second = tmp_path / "Другая музыка"
    first.mkdir()
    second.mkdir()
    make_tracks(first)
    tracks = make_tracks(second)
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.volume.setValue(0)
    calls = []

    def choose_folder(*args):
        calls.append(args[2])
        return str(first)

    def choose_files(*args):
        calls.append(args[2])
        return [str(tracks[0])], ""

    monkeypatch.setattr("app.ui.main_window.QFileDialog.getExistingDirectory", choose_folder)
    monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames", choose_files)
    try:
        window._add_folder()
        window._select_files(play_selected=play_selected)
        assert calls == ["", str(first)]
        assert window._dialog_directory() == str(second)
        monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames", lambda *args: ([], ""))
        window._open_files()
        assert window._dialog_directory() == str(second)
    finally:
        window.close()
    assert store.load()["last_directory"] == str(second)
    reopened = PlayerWindow(store)
    try:
        assert reopened._dialog_directory() == str(second)
        assert reopened.playlist.paths == []
        monkeypatch.setattr("app.ui.main_window.QFileDialog.getExistingDirectory",
                            lambda *args: calls.append(args[2]) or "")
        reopened._add_folder()
        assert calls[-1] == str(second)
        assert reopened._dialog_directory() == str(second)
    finally:
        reopened.close()


@pytest.mark.parametrize("directory", [None, 42, {}, "missing-folder", "bad\0path"])
def test_invalid_saved_directory_uses_dialog_default(qt_app, tmp_path, monkeypatch, directory):
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"last_directory": directory})
    window = PlayerWindow(store)
    calls = []
    monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames",
                        lambda *args: (calls.append(args[2]) or [], ""))
    try:
        window._add_files()
        assert calls == [""]
    finally:
        window.close()
