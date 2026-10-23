"""Сохранение реальной волны и повторное открытие без декодирования."""
import os
import time
import wave
from threading import Event

import numpy as np
from PySide6.QtTest import QTest

from app.services.waveform import WaveformService, calculate_peaks
from app.services.waveform_cache import WaveformCache


def test_cache_invalidation_and_corruption(tmp_path):
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"original")
    cache = WaveformCache(tmp_path / "cache")
    key = cache.key(audio)
    cache.save(key, [0, 0.5, 1])
    assert cache.load(key) == [0, 0.5, 1]
    stat = audio.stat()
    os.utime(audio, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    assert cache.key(audio) != key
    audio.write_bytes(b"changed size")
    assert cache.load(cache.key(audio)) is None
    entry = cache.directory / f"{key}.json"
    for content in ('broken', '{"version":2,"peaks":[NaN]}', '[]',
                    '{"version":2,"peaks":[true]}'):
        entry.write_text(content)
        assert cache.load(key) is None
        assert entry.exists()


def test_real_decode_cache_and_inflight_reuse(qt_app, tmp_path):
    audio = tmp_path / "tone.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x00\x10" * 16000)
    cache = WaveformCache(tmp_path / "cache")
    service = WaveformService(cache=cache)
    results = []
    service.ready.connect(results.append)
    service.open(audio)
    key = service._key
    service.open(audio)
    assert service._active and service._key == key
    for _ in range(400):
        if results:
            break
        QTest.qWait(20)
        time.sleep(0.001)
    assert results and max(results[0]) == 1
    assert cache.load(key) == results[0]
    service.open(audio)
    assert len(results) == 2  # Синхронный результат из памяти.
    service.cancel()
    restored = WaveformService(cache=cache)
    warm = []
    restored.ready.connect(warm.append)
    restored.open(audio)
    assert warm == [results[0]]  # Уже доступна до прохода event loop.
    assert not restored._active
    restored.cancel()
    assert not restored._active


def test_unwritable_cache_is_optional(tmp_path):
    directory = tmp_path / "file-instead-of-directory"
    directory.write_text("keep")
    cache = WaveformCache(directory)
    cache.save("example", [1])
    assert cache.load("example") is None
    assert directory.read_text() == "keep"


def test_stereo_phase_and_time_alignment(tmp_path):
    audio = tmp_path / "stereo.wav"
    mono = np.tile(np.array([12000, -12000], dtype=np.int16), 8000)
    mono[:8000] = 0
    stereo = np.column_stack((mono, -mono)).astype("<i2")
    with wave.open(str(audio), "wb") as stream:
        stream.setparams((2, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(stereo.tobytes())
    peaks = calculate_peaks(audio, Event())
    assert peaks == [0] * 10 + [1] * 10


def test_cancel_discards_queued_result(qt_app, tmp_path):
    service = WaveformService(cache=WaveformCache(tmp_path / "cache"))
    results, errors = [], []
    service.ready.connect(results.append)
    service.failed.connect(errors.append)
    audio = tmp_path / "broken.mp3"
    audio.write_bytes(b"broken")
    service.open(audio)
    token = service._token
    service.cancel()
    service._complete(token, [1], "")
    service._complete(token, [], "old failure")
    assert not results and not errors
    assert service.cache.load(service._key) is None
