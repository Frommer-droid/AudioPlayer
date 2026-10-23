"""Длительность по заголовкам и очистка только записей плейлиста."""
import os
import wave
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.services import duration
from app.ui.main_window import PlayerWindow
from tests.test_open_files import make_tracks
from tests.test_runtime import wait_until


def write_wav(path, seconds):
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x00\x10" * (16000 * seconds))


def test_duration_cache_reuses_headers_and_invalidates_changed_file(tmp_path, monkeypatch):
    path = tmp_path / "duration.wav"
    write_wav(path, 4)
    parser = duration.WaveStreamInfo
    calls = []

    def counting_parser(stream):
        calls.append(True)
        return parser(stream)

    monkeypatch.setattr(duration, "WaveStreamInfo", counting_parser)
    assert duration.read_duration_ms(path) == 4000
    assert duration.read_duration_ms(path) == 4000
    assert len(calls) == 1
    path.write_bytes(b"broken")
    assert duration.read_duration_ms(path) is None
    write_wav(path, 2)
    assert duration.read_duration_ms(path) == 2000
    assert len(calls) == 3
    assert duration.read_duration_ms(tmp_path / "missing.mp3") is None


def test_mp3_duration_header_does_not_modify_audio():
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    path = Path(source)
    before = path.read_bytes()
    assert 3900 <= duration.read_duration_ms(path) <= 4100
    assert path.read_bytes() == before


def test_duration_is_last_column_and_unknown_file_is_supported(qt_app, tmp_path):
    valid, second, _extra = make_tracks(tmp_path)
    second.write_bytes(b"broken")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    try:
        window.add_paths([valid, second])
        assert window.table.columnCount() == 4
        assert window.table.horizontalHeaderItem(3).text() == "Время"
        assert window.table.item(0, 3).text() == "00:04"
        for column in range(4):
            alignment = Qt.AlignmentFlag.AlignLeft if column == 1 else Qt.AlignmentFlag.AlignHCenter
            expected = alignment | Qt.AlignmentFlag.AlignVCenter
            assert window.table.horizontalHeaderItem(column).textAlignment() == expected
            assert window.table.item(0, column).textAlignment() == expected
        assert window.table.item(1, 3).text() == "—"
        for button in (window.library.add_files_button, window.library.add_folder_button,
                       window.library.remove_button, window.library.clear_button):
            assert not button.icon().isNull()
    finally:
        window.close()


def test_clear_all_stops_and_resets_without_deleting_files(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    before = {path: path.read_bytes() for path in paths}
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.volume.setValue(0)
    window.add_paths(paths)
    window.show()
    window._show_playlist()
    try:
        window.play(0)
        wait_until(lambda: window.player.media.position() > 100)
        window.table.selectRow(1)
        QTest.mouseClick(window.library.remove_button, Qt.MouseButton.LeftButton)
        assert window.playlist.paths == [paths[0], paths[2]]
        assert window.playlist.current == 0
        assert window.player.media.playbackState().name == "PlayingState"
        QTest.mouseClick(window.library.clear_button, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert window.playlist.paths == [] and window.playlist.current == -1
        assert window.table.rowCount() == 0
        assert window.count.text() == "Треков: 0"
        assert window.player.media.source().isEmpty()
        assert window.player.media.playbackState().name == "StoppedState"
        assert window.elapsed.text() == window.total.text() == "00:00"
        assert not window.wave.peaks and window.wave.duration == 0
        assert window.track_title.text() == "Откройте музыку"
        assert window.cover.image.isNull()
        assert not window.play_button.isEnabled()
        assert not window.library.clear_button.isEnabled()
        assert {path: path.read_bytes() for path in paths} == before
    finally:
        window.close()
    assert "playlist" not in store.load()
