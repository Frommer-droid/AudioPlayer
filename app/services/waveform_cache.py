"""Необязательный дисковый кеш; исходные аудиофайлы не изменяются."""
import hashlib
import json
import math
import os
import uuid
from pathlib import Path

from app.core.settings import ROOT


class WaveformCache:
    VERSION = 2

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else ROOT / ".cache" / "waveforms"

    def key(self, path):
        try:
            path = Path(path).resolve()
            stat = path.stat()
        except OSError:
            return None
        identity = [self.VERSION, os.path.normcase(str(path)), stat.st_size, stat.st_mtime_ns]
        return hashlib.sha256(json.dumps(identity).encode()).hexdigest()

    def load(self, key):
        if key is None:
            return None
        try:
            path = self.directory / f"{key}.json"
            if path.stat().st_size > 100000:
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            peaks = data["peaks"]
            if data["version"] != self.VERSION or not isinstance(peaks, list) or len(peaks) > 1800:
                return None
            if not all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in peaks):
                return None
            return peaks
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, key, peaks):
        if key is None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.directory / f"{key}.{uuid.uuid4().hex}.tmp"
            temporary.write_text(json.dumps({"version": self.VERSION, "peaks": peaks}), encoding="utf-8")
            temporary.replace(self.directory / f"{key}.json")
        except OSError:
            pass  # Недоступный кеш не мешает воспроизведению и построению волны.
