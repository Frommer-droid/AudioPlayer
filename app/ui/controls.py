"""Компактные векторные кнопки, обложка и строка заголовка."""
from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from app.ui.application_icon import ICON_PATH
from app.ui.icon_assets import create_renderer
from app.ui.theme.colors import THEME_COLORS as C


class LogoButton(QAbstractButton):
    """Цвет знака показывает закрепление, независимо от hover/focus."""

    def __init__(self, callback):
        super().__init__()
        self.setFixedSize(22, 22)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Поверх всех окон")
        data = ICON_PATH.with_suffix(".svg").read_bytes()
        self._renderers = {
            checked: QSvgRenderer(QByteArray(data.replace(b"#E68C24", color.encode("ascii"))), self)
            for checked, color in ((False, C["text_strong"]), (True, C["accent"]))
        }
        self.clicked.connect(callback)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderers[self.isChecked()].render(painter, QRectF(1, 1, 20, 20))


class IconButton(QAbstractButton):
    """Единый набор SVG с независимыми размерами иконки и области нажатия."""
    def __init__(self, symbol, label, callback, size=34, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self._renderers = {}
        self.setText(label)
        self.setAccessibleName(label)
        self.setAccessibleDescription(label)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(callback)

    def paintEvent(self, event):
        color = C["text_strong"]
        if not self.isEnabled():
            color = C["disabled_text"]
        elif self.isDown() or self.isChecked():
            color = C["accent"]
        elif self.symbol in ("menu", "settings", "speaker", "min", "max", "close"):
            color = C["muted"]
        if self.underMouse() and self.isEnabled():
            color = C["accent"] if self.symbol != "close" else C["danger"]
        symbol = "muted" if self.symbol == "speaker" and self.isChecked() else self.symbol
        key = (symbol, color)
        if key not in self._renderers:
            self._renderers[key] = create_renderer(symbol, color, self)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = self.symbol in ("play", "pause_circle")
        if circle:
            painter.setPen(QPen(QColor(color), 2.25))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF((self.width() - 42) / 2, (self.height() - 42) / 2, 42, 42))
        size = 26 if circle else 16 if self.symbol in ("menu", "min", "max", "close") else 22
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        self._renderers[key].render(painter, rect)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()


class TransportButton(IconButton):
    """ЛКМ и клавиатура переключают play/pause, ПКМ останавливает трек."""
    stopRequested = Signal()

    def __init__(self, toggle, stop):
        super().__init__("play", "Воспроизвести", toggle, 54)
        self._right_pressed = False
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.stopRequested.connect(stop)
        self.set_playback_state(False, False)

    def set_playback_state(self, playing, paused):
        self.symbol = "pause_circle" if playing else "play"
        action = "Пауза" if playing else "Продолжить" if paused else "Воспроизвести"
        self.setText(action)
        self.setAccessibleName(f"{action}. Правая кнопка мыши — остановить")
        self.setAccessibleDescription(f"ЛКМ — {action.lower()}; ПКМ — остановить")
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.isEnabled():
            self._right_pressed = True
            self.setDown(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            pressed = self._right_pressed
            self._right_pressed = False
            self.setDown(False)
            if pressed and self.isEnabled() and self.rect().contains(event.position().toPoint()):
                self.stopRequested.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        event.accept()


class CoverButton(QAbstractButton):
    def __init__(self, callback):
        super().__init__()
        self.setFixedSize(60, 60)
        self.setAccessibleName("Обложка. Открыть файл")
        self.setAccessibleDescription("Левая кнопка мыши — открыть файл")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image = QImage()
        self.clicked.connect(callback)

    def set_cover(self, data):
        self.image = QImage.fromData(data) if data else QImage()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.image.isNull():
            image = self.image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation)
            x, y = (image.width() - self.width()) // 2, (image.height() - self.height()) // 2
            painter.drawImage(self.rect(), image, image.rect().adjusted(x, y, -x, -y))
        else:
            painter.fillRect(self.rect(), QColor(C["surface"]))
            painter.translate(self.width() / 2, self.height() / 2)
            painter.scale(self.width() / 88, self.height() / 88)
            painter.setPen(QPen(QColor(C["border"]), 1))
            for radius in (37, 32, 26):
                painter.drawEllipse(QPointF(0, 0), radius, radius)
            painter.setBrush(QColor(C["accent"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(0, 0), 10, 10)
            painter.setBrush(QColor(C["surface"]))
            painter.drawEllipse(QPointF(0, 0), 2, 2)
            painter.resetTransform()
        painter.setPen(QPen(QColor(C["border"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class ElidedLabel(QLabel):
    textChanged = Signal()

    def __init__(self, text=""):
        super().__init__(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        changed = text != self.text()
        super().setText(text)
        self.setAccessibleDescription(text)
        if changed:
            self.textChanged.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().windowText().color())
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(self.rect(), self.alignment(), text)


class DurationLabel(ElidedLabel):
    clicked = Signal()
    rightClicked = Signal()

    def mousePressEvent(self, event):
        self._pressed = event.button()
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            pressed = getattr(self, "_pressed", None)
            self._pressed = None
            if pressed == event.button() and self.rect().contains(event.position().toPoint()):
                signal = self.clicked if event.button() == Qt.MouseButton.LeftButton else self.rightClicked
                signal.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class TitleBar(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()


class SideGrip(QWidget):
    def __init__(self, parent, edge):
        super().__init__(parent)
        self.edge = edge
        self._drag_start = None
        self.setObjectName("resizeGrip")
        horizontal = bool(edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge))
        vertical = bool(edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge))
        if horizontal and vertical:
            forward = bool(edge & Qt.Edge.LeftEdge) == bool(edge & Qt.Edge.TopEdge)
            cursor = Qt.CursorShape.SizeFDiagCursor if forward else Qt.CursorShape.SizeBDiagCursor
        else:
            cursor = Qt.CursorShape.SizeVerCursor if vertical else Qt.CursorShape.SizeHorCursor
        self.setCursor(cursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._start_geometry = self.window().geometry()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None and event.buttons() & Qt.MouseButton.LeftButton:
            window = self.window()
            position = event.globalPosition().toPoint()
            start = self._start_geometry
            width, height, x, y = start.width(), start.height(), start.x(), start.y()
            if self.edge & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
                delta = position.y() - self._drag_start.y()
                change = -delta if self.edge & Qt.Edge.TopEdge else delta
                height = max(window.minimumHeight(), min(window.maximumHeight(), start.height() + change))
                y = start.y() + start.height() - height if self.edge & Qt.Edge.TopEdge else start.y()
            if self.edge & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
                delta = position.x() - self._drag_start.x()
                change = -delta if self.edge & Qt.Edge.LeftEdge else delta
                width = max(window.minimumWidth(), min(window.maximumWidth(), start.width() + change))
                x = start.x() + start.width() - width if self.edge & Qt.Edge.LeftEdge else start.x()
            window.setGeometry(x, y, width, height)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)
