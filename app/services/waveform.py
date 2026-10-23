"""Быстрый независимый анализ аудио в рабочем потоке и чтение из кеша."""
from pathlib import Path
from threading import Event

import av
import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app.services.waveform_cache import WaveformCache


def calculate_peaks(path, cancelled):
    """Читаем с максимальной скоростью; храним только пики за 50 мс и хвост."""
    peaks = []
    tail = np.empty(0, dtype=np.float32)
    if cancelled.is_set():
        return None
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            if cancelled.is_set():
                return None
            samples = np.abs(frame.to_ndarray().astype(np.float32, copy=False))
            np.nan_to_num(samples, copy=False, nan=0, posinf=0, neginf=0)
            # Packed WAV и planar MP3: максимум каналов сохраняет также
            # противофазный стереосигнал, исчезающий при усреднении.
            if frame.format.is_planar:
                samples = samples.max(axis=0)
            else:
                samples = samples.reshape(-1, len(frame.layout.channels)).max(axis=1)
            if tail.size:
                samples = np.concatenate((tail, samples))
            window = max(1, frame.sample_rate // 20)
            complete = samples.size // window * window
            if complete:
                peaks.extend(samples[:complete].reshape(-1, window).max(axis=1).tolist())
            tail = samples[complete:].copy()
    if tail.size:
        peaks.append(float(tail.max()))
    count = min(1800, len(peaks))
    if not count:
        return []
    values = np.asarray(peaks, dtype=np.float32)
    reduced = np.maximum.reduceat(values, np.arange(count) * len(peaks) // count)
    return (reduced / (float(reduced.max()) or 1)).tolist()


class _Signals(QObject):
    completed = Signal(int, list, str)


class _Analysis(QRunnable):
    def __init__(self, path, token, cancelled, signals):
        super().__init__()
        self.path, self.token = path, token
        self.cancelled, self.signals = cancelled, signals

    def run(self):
        try:
            peaks = calculate_peaks(self.path, self.cancelled)
            if peaks is not None and not self.cancelled.is_set():
                self.signals.completed.emit(self.token, peaks, "")
        except (av.FFmpegError, OSError, ValueError, IndexError) as error:
            if not self.cancelled.is_set():
                self.signals.completed.emit(self.token, [], str(error))


class WaveformService(QObject):
    ready = Signal(list)
    failed = Signal(str)

    def __init__(self, parent=None, cache=None):
        super().__init__(parent)
        self.cache = cache if cache is not None else WaveformCache()
        self._signals = _Signals()
        self._signals.completed.connect(self._complete)
        self._cancelled = Event()
        self._token = 0
        self._key = None
        self._path = None
        self._result = None
        self._active = False

    def cancel(self):
        self._cancelled.set()
        self._token += 1
        self._active = False

    def open(self, path):
        key = self.cache.key(path)
        if key is not None and key == self._key:
            if self._active:
                return
            if self._result is not None:
                self.ready.emit(list(self._result))
                return
        self.cancel()
        self._key, self._path = key, Path(path)
        self._result = self.cache.load(key)
        if self._result is not None:
            self.ready.emit(list(self._result))
            return
        self._active = True
        self._cancelled = Event()
        QThreadPool.globalInstance().start(
            _Analysis(self._path, self._token, self._cancelled, self._signals))

    @Slot(int, list, str)
    def _complete(self, token, peaks, error):
        if token != self._token or not self._active:
            return
        self._active = False
        if error:
            self.failed.emit(error)
            return
        self._result = peaks
        if self.cache.key(self._path) == self._key:
            self.cache.save(self._key, peaks)
        self.ready.emit(list(peaks))
