"""Проверки реального аудиодвижка и интерфейса Qt."""
import math
import os
import struct
import time
import wave
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtMultimedia import QAudioBufferOutput, QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.settings import SettingsStore
from app.services.player import PlayerService
from app.services.waveform import WaveformService
from app.ui.main_window import PlayerWindow
from app.ui.waveform import WaveformWidget


def wait_until(predicate, timeout=8000):
    for _ in range(timeout // 20):
        if predicate():
            return
        QTest.qWait(20)
        time.sleep(0.001)  # QTest.qWait удерживает GIL; дать исполниться Python worker.
    assert predicate(), "Не дождались ожидаемого события Qt"


@pytest.fixture
def wav_file(tmp_path):
    path = tmp_path / "тест с пробелами.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        data = [int(12000 * (0.2 + 0.8 * i / 64000) * math.sin(2 * math.pi * 440 * i / 16000))
                for i in range(64000)]
        audio.writeframes(struct.pack(f"<{len(data)}h", *data))
    return path


@pytest.mark.parametrize("extension", ["wav", "mp3"])
def test_real_decode_waveform_and_playback(qt_app, wav_file, extension):
    if extension == "mp3":
        value = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
        if not value:
            pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE для проверки реального MP3")
        path = Path(value)
        assert path.is_file()
    else:
        path = wav_file
    waveform = WaveformService()
    peaks, errors = [], []
    waveform.ready.connect(peaks.append)
    waveform.failed.connect(errors.append)
    waveform.open(path)
    wait_until(lambda: bool(peaks or errors))
    assert not errors
    assert len(peaks[0]) > 5
    assert max(peaks[0]) == pytest.approx(1)
    waveform.cancel()

    player = PlayerService()
    player.audio.setVolume(0)
    output = QAudioBufferOutput(player)
    player.media.setAudioBufferOutput(output)
    buffers = []
    output.audioBufferReceived.connect(lambda buffer: buffers.append(buffer.sampleCount()))
    player.failed.connect(errors.append)
    player.open(path)
    wait_until(lambda: player.media.position() > 150 or bool(errors))
    assert not errors
    assert player.media.duration() >= 3000
    assert sum(buffers) > 0
    player.toggle()
    assert player.media.playbackState() == QMediaPlayer.PlaybackState.PausedState
    player.media.setPosition(2000)
    wait_until(lambda: abs(player.media.position() - 2000) < 200)
    player.stop()
    assert player.media.playbackState() == QMediaPlayer.PlaybackState.StoppedState


def test_actual_wheel_event(qt_app):
    widget = WaveformWidget()
    widget.duration, widget.position = 60000, 10000
    changes = []
    widget.seek.connect(changes.append)
    event = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(), QPoint(0, -120),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    assert changes == [15000]
    widget.close()


def test_waveform_while_playing_in_window(qt_app, tmp_path):
    value = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not value:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths([value])
    window.show()
    try:
        window.play(0)
        wait_until(lambda: bool(window.wave.peaks), timeout=12000)
        wait_until(lambda: window.wave.duration > 0)
        assert window.wave.duration > 0
        window.grab().save(str(tmp_path / "player-with-waveform.png"))
    finally:
        window.close()


def test_native_geometry_five_cycles(qt_app, tmp_path):
    if QApplication.platformName() == "offscreen":
        pytest.skip("Нужна настоящая оконная рамка Windows")
    store = SettingsStore(tmp_path / "settings.json")
    original = None
    for i in range(5):
        window = PlayerWindow(store)
        if not i:
            window.resize(1000, 720)
            window.move(140, 100)
        window.show()
        QTest.qWait(90)
        geometry = (window.pos().x(), window.pos().y(), window.width(), window.height())
        if original is None:
            original = geometry
        assert geometry == original
        window.close()
        qt_app.processEvents()


def test_corrupt_settings_and_ignore_legacy_playlist(qt_app, tmp_path, wav_file):
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"volume": "broken", "playlist": [str(wav_file)], "window": {"geometry": 45}})
    window = PlayerWindow(store)
    assert window.volume.value() == 65
    assert window.table.rowCount() == 0
    assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.StoppedState
    window.close()
    assert "playlist" not in store.load()
