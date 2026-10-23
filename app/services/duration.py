"""Кеш длительности по заголовкам, без декодирования аудио."""
import math
from functools import lru_cache
from pathlib import Path

import av
import mutagen
from mutagen.mp3 import MPEGInfo
from mutagen.wave import WaveStreamInfo


def read_duration_ms(path):
    try:
        path = Path(path).resolve()
        stat = path.stat()
        return _duration_from_header(str(path), stat.st_size, stat.st_mtime_ns)
    except OSError:
        return None


@lru_cache(maxsize=4096)
def _duration_from_header(path, size, modified_ns):
    # size/modified_ns участвуют в ключе, чтобы изменённый файл перечитывался.
    try:
        parser = {".mp3": MPEGInfo, ".wav": WaveStreamInfo}.get(Path(path).suffix.lower())
        if parser is not None:
            with open(path, "rb") as stream:
                seconds = parser(stream).length
        else:
            with av.open(path) as container:
                if not container.streams.audio:
                    return None
                stream = container.streams.audio[0]
                if stream.duration is not None and stream.time_base is not None:
                    seconds = float(stream.duration * stream.time_base)
                elif container.duration is not None:
                    seconds = container.duration / av.time_base
                else:
                    return None
        if not math.isfinite(seconds) or seconds < 0:
            return None
        return round(seconds * 1000)
    except (OSError, ValueError, OverflowError, mutagen.MutagenError, av.FFmpegError):
        return None
