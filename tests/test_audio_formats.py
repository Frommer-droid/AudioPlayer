"""Проверка новых форматов на настоящих файлах: теги, длительность, волна и PCM."""
import os
import subprocess
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtMultimedia import QAudioBufferOutput

from app.core.playlist import AUDIO_FILE_FILTER, SUPPORTED, Playlist
from app.services.duration import read_duration_ms
from app.services.metadata import read_metadata
from app.services.player import PlayerService
from app.services.waveform import calculate_peaks
from tests.test_runtime import wait_until


@pytest.mark.parametrize("extension,codec", [
    ("flac", "flac"), ("ogg", "libvorbis"), ("oga", "flac"), ("opus", "libopus"),
    ("m4a", "aac"), ("m4a", "alac"), ("aac", "aac"), ("wma", "wmav2"),
    ("aif", "pcm_s16be"), ("aiff", "pcm_s16be"), ("wv", "wavpack"),
])
def test_audio_format_pipeline(qt_app, tmp_path, extension, codec):
    ffmpeg = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
    if not ffmpeg.is_file():
        pytest.skip("Нужен FFmpeg для генерации временного fixture")
    path = tmp_path / f"Музыка с пробелами.{extension}"
    extra = ["-write_id3v2", "1"] if extension in ("aif", "aiff") else []
    subprocess.run([str(ffmpeg), "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=3:sample_rate=48000", "-c:a", codec,
                    "-metadata", "title=Test title", "-metadata", "artist=Test artist",
                    "-metadata", "album=Test album", *extra, str(path)], check=True, timeout=30)
    check_pipeline(path, qt_app)
    metadata = read_metadata(path)
    assert metadata.sample_rate == 48000
    if extension != "aac":  # ADTS не содержит контейнерных тегов.
        assert metadata.heading == "Test album · Test artist · Test title"


def check_pipeline(path, qt_app):
    original = path.read_bytes()
    assert path.suffix in SUPPORTED and f"*{path.suffix}" in AUDIO_FILE_FILTER
    playlist = Playlist()
    assert playlist.add([path]) == 1
    assert 2700 <= read_duration_ms(path) <= 3500
    peaks = calculate_peaks(path, Event())
    assert len(peaks) > 20 and max(peaks) == pytest.approx(1)
    player = PlayerService()
    player.audio.setVolume(0)
    output = QAudioBufferOutput(player)
    player.media.setAudioBufferOutput(output)
    samples, errors = [], []
    output.audioBufferReceived.connect(lambda buffer: samples.append(buffer.sampleCount()))
    player.failed.connect(errors.append)
    try:
        player.open(path)
        wait_until(lambda: sum(samples) > 0 or bool(errors))
        assert not errors
        assert sum(samples) > 0
        player.media.setPosition(1500)
        wait_until(lambda: player.media.position() >= 1400 or bool(errors))
        assert not errors
    finally:
        player.stop(reload=False)
    assert path.read_bytes() == original


def test_ape_pipeline(qt_app):
    value = os.environ.get("AUDIOPLAYER_APE_FIXTURE")
    if not value:
        pytest.skip("Задайте AUDIOPLAYER_APE_FIXTURE для реального APE")
    path = Path(value)
    assert path.is_file()
    # Внешний sample может быть длиннее тестового синуса.
    assert read_duration_ms(path) > 0
    assert calculate_peaks(path, Event())
    player = PlayerService()
    player.audio.setVolume(0)
    output = QAudioBufferOutput(player)
    player.media.setAudioBufferOutput(output)
    samples, errors = [], []
    output.audioBufferReceived.connect(lambda buffer: samples.append(buffer.sampleCount()))
    player.failed.connect(errors.append)
    try:
        player.open(path)
        wait_until(lambda: sum(samples) > 0 or bool(errors))
        assert not errors and sum(samples) > 0
    finally:
        player.stop(reload=False)
