"""Плейлист без привязки к интерфейсу и аудиодвижку."""
from pathlib import Path
from random import choice

SUPPORTED = {".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac",
             ".wma", ".aif", ".aiff", ".ape", ".wv"}
AUDIO_FILE_FILTER = "Аудиофайлы (" + " ".join(f"*{ext}" for ext in sorted(SUPPORTED)) + ")"


class Playlist:
    def __init__(self, name="Плейлист"):
        self.name = name
        self.search = ""
        self.selection = 0
        self.paths: list[Path] = []
        self.original_paths: list[Path] = []
        self.sort_column = None
        self.sort_descending = False
        self.current = -1
        self.visited: set[Path] = set()

    def add(self, paths) -> int:
        known = {str(p).casefold() for p in self.paths}
        count = 0
        for value in paths:
            try:
                path = Path(value).resolve()
            except (OSError, ValueError, TypeError):
                continue
            key = str(path).casefold()
            if path.is_file() and path.suffix.lower() in SUPPORTED and key not in known:
                self.paths.append(path)
                self.original_paths.append(path)
                known.add(key)
                count += 1
        return count

    def sort(self, key, reverse=False):
        """Меняет очередь, сохраняя текущий и выбранный файлы."""
        current = self.paths[self.current] if 0 <= self.current < len(self.paths) else None
        selected = self.paths[self.selection] if 0 <= self.selection < len(self.paths) else None
        self.paths.sort(key=key, reverse=reverse)
        self.current = self.paths.index(current) if current is not None else -1
        self.selection = self.paths.index(selected) if selected is not None else 0

    def next_index(self, direction=1, shuffle=False, repeat=False) -> int | None:
        if not self.paths:
            return None
        if shuffle and direction > 0:
            if 0 <= self.current < len(self.paths):
                self.visited.add(self.paths[self.current])
            candidates = [i for i, path in enumerate(self.paths) if path not in self.visited]
            if not candidates and repeat:
                self.visited.clear()
                candidates = [i for i in range(len(self.paths)) if i != self.current] or [0]
            return choice(candidates) if candidates else None
        if self.current < 0:
            return 0
        index = self.current + direction
        if 0 <= index < len(self.paths):
            return index
        return index % len(self.paths) if repeat else None

    def remove(self, indices):
        selected = set(indices)
        current_path = self.paths[self.current] if 0 <= self.current < len(self.paths) else None
        self.paths = [p for i, p in enumerate(self.paths) if i not in selected]
        remaining = set(self.paths)
        self.original_paths = [p for p in self.original_paths if p in remaining]
        self.current = self.paths.index(current_path) if current_path in self.paths else -1
        self.visited.intersection_update(self.paths)


def wheel_seek_position(position: int, duration: int, delta: float, inverted=False, step=5000) -> int:
    """Физическое движение колеса на себя всегда ведёт вперёд."""
    physical_delta = -delta if inverted else delta
    return max(0, min(duration, round(position - physical_delta / 120 * step)))


def format_time(milliseconds: int) -> str:
    seconds = max(0, milliseconds // 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02}:{seconds:02}"
