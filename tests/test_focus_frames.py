"""Фокус не добавляет рамок, клавиатура и drag продолжают работать."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QSlider, QVBoxLayout, QWidget

from app.ui.controls import IconButton
from app.ui.waveform import WaveformWidget


def test_focus_has_no_frame_and_controls_remain_interactive(qt_app, tmp_path):
    window = QWidget()
    layout = QVBoxLayout(window)
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setFixedHeight(24)
    slider.setRange(0, 100)
    slider.setValue(50)
    clicked = []
    icon = IconButton("settings", "Настройки", lambda: clicked.append(True))
    button = QPushButton("Добавить файлы")
    wave = WaveformWidget()
    wave.duration = 60000
    wave.set_peaks([0.2, 0.8, 0.4] * 100)
    for widget in (slider, icon, button, wave):
        layout.addWidget(widget)
    window.resize(500, 200)
    window.show()
    window.activateWindow()
    QTest.qWait(100)
    try:
        for widget in (slider, icon, button, wave):
            widget.clearFocus()
            before = widget.grab().toImage()
            widget.setFocus(Qt.FocusReason.TabFocusReason)
            assert widget.hasFocus()
            assert widget.grab().toImage() == before
        slider.setFocus()
        QTest.mousePress(slider, Qt.MouseButton.LeftButton,
                         pos=QPoint(slider.width() // 2, slider.height() // 2))
        QTest.mouseMove(slider, QPoint(slider.width() * 3 // 4, slider.height() // 2))
        QTest.mouseRelease(slider, Qt.MouseButton.LeftButton,
                           pos=QPoint(slider.width() * 3 // 4, slider.height() // 2))
        assert slider.value() > 50
        focused = slider.grab().toImage()
        slider.clearFocus()
        assert slider.grab().toImage() == focused
        value = slider.value()
        slider.setFocus()
        QTest.keyClick(slider, Qt.Key.Key_Right)
        assert slider.value() == value + 1
        icon.setFocus()
        QTest.keyClick(icon, Qt.Key.Key_Space)
        assert clicked == [True]
        changes = []
        wave.seek.connect(changes.append)
        wave.setFocus()
        QTest.keyClick(wave, Qt.Key.Key_Right)
        assert changes == [5000]
        window.grab().save(str(tmp_path / "controls-without-focus-frames.png"))
    finally:
        window.close()
