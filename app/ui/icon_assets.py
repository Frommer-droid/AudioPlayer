"""Локальные Tabler SVG: единая геометрия и цвет из темы, без сетевого runtime."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICON_FILES = {
    "lyrics": "lyrics",
    "search": "search",
    "play": "player-play", "pause_circle": "player-pause",
    "previous": "player-skip-back", "next": "player-skip-forward",
    "repeat": "repeat", "repeat_one": "repeat-once", "playlist_play": "playlist", "ab": "a-b-2",
    "shuffle": "arrows-shuffle", "speaker": "volume", "muted": "volume-off",
    "settings": "settings", "menu": "dots", "min": "minus", "max": "square", "close": "x",
    "add_files": "file-plus", "add_folder": "folder-plus", "clear_playlist": "playlist-x",
    "increase": "plus", "decrease": "minus", "arrow_down": "arrow-down", "arrow_up": "arrow-up",
}


@lru_cache(maxsize=32)
def icon_bytes(symbol):
    return (Path(__file__).with_name("icons") / f"{ICON_FILES[symbol]}.svg").read_bytes()


def create_renderer(symbol, color, parent=None):
    data = icon_bytes(symbol).replace(b"currentColor", color.encode("ascii"))
    renderer = QSvgRenderer(QByteArray(data), parent)
    if not renderer.isValid():
        raise ValueError(f"Некорректная SVG-иконка: {symbol}")
    return renderer


def button_icon(symbol, color):
    """Tabler для стандартных текстовых кнопок, с запасом разрешения для DPI."""
    renderer = create_renderer(symbol, color)
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
