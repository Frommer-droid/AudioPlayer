"""Реальное завершение WAV: остановка, очередь, циклический список и один трек."""
import math
import struct
import wave

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtMultimedia import QMediaPlayer

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow


def wait_until(predicate):
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    poll.start()
    timeout.start(8000)
    loop.exec()
    poll.stop()
    timeout.stop()
    assert predicate()


@pytest.mark.parametrize("mode,start,expected", [
    ("off", 0, 0), ("off", 1, 1),
    ("queue", 0, 1), ("queue", 1, 1),
    ("playlist", 0, 1), ("playlist", 1, 0),
    ("track", 0, 0), ("track", 1, 1),
])
def test_real_end_of_media_obeys_selected_mode(qt_app, tmp_path, mode, start, expected):
    paths = []
    for index in range(2):
        path = tmp_path / f"track{index}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            samples = [int(8000 * math.sin(2 * math.pi * 440 * i / 8000)) for i in range(16000)]
            audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        paths.append(path)
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.show()
    window.volume.setValue(0)
    window.add_paths(paths)
    window._set_repeat_mode(mode)
    endings = []
    window.player.ended.connect(lambda: endings.append(True))
    try:
        window.play(start)
        wait_until(lambda: bool(endings))
        assert window.playlist.current == expected
        assert window.player.media.source().toLocalFile() == str(paths[expected]).replace("\\", "/")
        stops = mode == "off" or (mode == "queue" and start == 1)
        if stops:
            wait_until(lambda: window.player.media.position() == 0 and window.wave.position == 0)
            assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.StoppedState
            assert window.elapsed.text() == "00:00"
            assert window.play_button.symbol == "play"
            assert window.wave.peaks
            image = window.wave.grab().toImage()
            assert not any(image.pixelColor(x, y).red() > 180
                           and 70 < image.pixelColor(x, y).green() < 190
                           and image.pixelColor(x, y).blue() < 70
                           for x in range(image.width()) for y in range(image.height()))
        else:
            wait_until(lambda: window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState)
        if mode == "queue" and start == 0:
            wait_until(lambda: len(endings) >= 2)
            wait_until(lambda: window.player.media.position() == 0 and window.wave.position == 0)
            assert window.playlist.current == 1
            assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.StoppedState
        if stops:
            window._toggle()
            wait_until(lambda: window.player.media.position() > 0)
            assert window.playlist.current == expected
            assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    finally:
        window.close()
    restored = PlayerWindow(store)
    try:
        assert restored._repeat_mode == mode
    finally:
        restored.close()
