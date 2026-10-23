"""Общий знак Windows/заголовка/трея и восстановление окна без смещения."""
import struct

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QSystemTrayIcon

from app.core.settings import SettingsStore
from app.ui.application_icon import ICON_PATH, application_icon
from app.ui.main_window import PlayerWindow


def test_multisize_icon_decodes(qt_app):
    data = ICON_PATH.read_bytes()
    assert struct.unpack_from("<HHH", data) == (0, 1, 9)
    icon = application_icon()
    assert not icon.isNull()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        assert QSize(size, size) in icon.availableSizes()
        image = icon.pixmap(size, size).toImage()
        assert not image.isNull()
        assert image.pixelColor(0, 0).alpha() == 0
        assert any(image.pixelColor(x, size // 2).red() > 200 for x in range(size))
    assert not QIcon(str(ICON_PATH.with_suffix(".svg"))).isNull()


def test_tray_restore_and_exit(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    QTest.qWait(60)
    try:
        assert not window.windowIcon().isNull()
        assert not window.brand_mark.grab().isNull()
        assert not window.tray.icon().isNull()
        assert window.tray.contextMenu() is window.tray_menu
        assert window.tray.isVisible() == QSystemTrayIcon.isSystemTrayAvailable()
        position, size = window.pos(), window.size()
        for _ in range(5):
            window.showMinimized()
            QTest.qWait(40)
            window.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
            QTest.qWait(40)
            assert window.isVisible() and not window.isMinimized()
            assert window.pos() == position and window.size() == size
        window.tray_menu.actions()[-1].trigger()
        assert not window.isVisible() and not window.tray.isVisible()
        assert (tmp_path / "settings.json").exists()
    finally:
        window.close()
