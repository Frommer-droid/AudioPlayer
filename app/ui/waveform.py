"""Волна-таймлайн: щелчок, перетаскивание и колесо для перемотки."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.core.playlist import wheel_seek_position
from app.ui.theme.colors import THEME_COLORS as C


class WaveformWidget(QWidget):
    seek = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(28)
        self.setMaximumHeight(42)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName("Звуковая волна и перемотка")
        self.setAccessibleDescription("Колесо на себя — вперёд, от себя — назад. Щелчок — переход по треку.")
        self.peaks = []
        self.position = 0
        self.duration = 0
        self.step = 5000
        self.message = "Добавьте аудиофайлы"

    def set_peaks(self, peaks):
        self.peaks = peaks
        self.message = "Нет данных волны" if not peaks else ""
        self.update()

    def set_position(self, position):
        self.position = position
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(C["background"]))
        width, height = self.width(), self.height()
        center = height / 2
        fraction = min(1, self.position / self.duration) if self.duration else 0
        painter.setPen(QPen(QColor(C["border"]), 0.6))
        painter.drawLine(QPointF(1, center), QPointF(width - 1, center))
        if self.peaks:
            bars = max(1, width - 4)
            envelope = []
            for i in range(bars):
                begin = i * len(self.peaks) // bars
                end = max(begin + 1, (i + 1) * len(self.peaks) // bars)
                peak = max(self.peaks[begin:end], default=0)
                envelope.append(max(0.6, peak * (height - 5) / 2))
            path = QPainterPath(QPointF(2, center))
            for i, extent in enumerate(envelope):
                path.lineTo(2 + i, center - extent)
            for i in range(bars - 1, -1, -1):
                path.lineTo(2 + i, center + envelope[i])
            path.closeSubpath()
            painter.fillPath(path, QColor(C["scrollbar"]))
            painter.save()
            painter.setClipRect(QRectF(0, 0, fraction * width, height))
            painter.fillPath(path, QColor(C["accent"]))
            painter.restore()
        else:
            painter.setPen(QColor(C["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)

    def _seek_at(self, x):
        if self.duration:
            ratio = max(0, min(1, (x - 2) / max(1, self.width() - 4)))
            self.seek.emit(round(ratio * self.duration))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.update()
            self._seek_at(event.position().x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._seek_at(event.position().x())

    def wheelEvent(self, event):
        if self.duration:
            delta = event.angleDelta().y() or event.pixelDelta().y() * 3
            position = wheel_seek_position(self.position, self.duration, delta, event.inverted(), self.step)
            self.seek.emit(position)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            delta = -self.step if event.key() == Qt.Key.Key_Left else self.step
            self.seek.emit(max(0, min(self.duration, self.position + delta)))
        elif event.key() in (Qt.Key.Key_Home, Qt.Key.Key_End):
            self.seek.emit(0 if event.key() == Qt.Key.Key_Home else self.duration)
        else:
            super().keyPressEvent(event)
