"""Read a fallback cover from the audio directory without changing files."""
from pathlib import Path

from PySide6.QtGui import QImage

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
COVER_NAMES = {"cover": 0, "folder": 1, "front": 2}


def folder_cover(track: Path) -> bytes:
    try:
        candidates = sorted(
            (path for path in track.parent.iterdir()
             if path.suffix.casefold() in IMAGE_EXTENSIONS and path.is_file()),
            key=lambda path: (COVER_NAMES.get(path.stem.casefold(), 3),
                              path.name.casefold(), path.name),
        )
    except OSError:
        return b""
    for path in candidates:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if not QImage.fromData(data).isNull():
            return data
    return b""
