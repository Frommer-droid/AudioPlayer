"""Компактные настройки: stepper, ручной ввод, применение и сохранение."""
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow


def test_compact_settings_stepper_and_persistence(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.show()
    window._show_settings()
    dialog = window.preferences
    try:
        assert dialog.isVisible()
        assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert dialog.width() == 430 and dialog.height() < 300
        assert dialog.wheel_step.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons
        assert dialog.wheel_step.lineEdit().width() >= 60
        QTest.mouseClick(dialog.increase, Qt.MouseButton.LeftButton)
        assert dialog.wheel_step.value() == 6 and window.wave.step == 6000
        QTest.mouseClick(dialog.decrease, Qt.MouseButton.LeftButton)
        assert dialog.wheel_step.value() == 5
        dialog.wheel_step.setValue(1)
        assert not dialog.decrease.isEnabled()
        dialog.wheel_step.setValue(60)
        assert not dialog.increase.isEnabled()
        editor = dialog.wheel_step.lineEdit()
        QTest.mouseClick(editor, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        editor.selectAll()
        QTest.keyClicks(editor, "12")
        QTest.keyClick(editor, Qt.Key.Key_Tab)
        assert dialog.wheel_step.value() == 12 and window.wave.step == 12000
        QTest.keyClick(dialog, Qt.Key.Key_Escape)
        assert not dialog.isVisible()
    finally:
        window.close()
    assert store.load()["wheel_step"] == 12
