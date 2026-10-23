"""Воспроизводимый multi-resolution ICO из SVG средствами проектного Qt."""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]


def main():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    assets = ROOT / "app" / "ui" / "assets"
    renderer = QSvgRenderer(str(assets / "audioplayer.svg"))
    if not renderer.isValid():
        raise ValueError("Invalid application SVG")
    frames = []
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise RuntimeError("PNG export failed")
        frames.append(bytes(data))
        if size == 256:
            image.save(str(assets / "audioplayer.png"))
    offset = 6 + 16 * len(frames)
    entries = []
    for size, frame in zip(sizes, frames, strict=True):
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                                   1, 32, len(frame), offset))
        offset += len(frame)
    (assets / "audioplayer.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(frames)) + b"".join(entries) + b"".join(frames))
    app.quit()


if __name__ == "__main__":
    main()
