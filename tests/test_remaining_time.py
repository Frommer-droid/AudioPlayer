"""ПКМ переключает общую длительность и остаток, не вызывая действие ЛКМ."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from app.ui.theme.colors import THEME_COLORS
from tests.test_open_files import make_tracks
from tests.test_runtime import wait_until


def test_remaining_time_click_updates_bounds_and_lyrics(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window.library.set_lyrics("Текст песни")
    try:
        window._duration(262_000)
        window._position(188_000)
        assert window.total.text() == "01:14"
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.text() == "04:22"
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.text() == "01:14"
        assert not window.library.isVisible()
        assert window.total.fontMetrics().horizontalAdvance(window.total.text()) <= window.total.width()
        window._position(200_000)
        assert window.total.text() == "01:02"
        window._duration(300_000)
        assert window.total.text() == "01:40"
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert window.library.isVisible() and window.library.pages.currentIndex() == 1
        assert window.total.text() == "01:40"
        QTest.mousePress(window.total, Qt.MouseButton.RightButton)
        QTest.mouseRelease(window.total, Qt.MouseButton.RightButton, pos=QPoint(-2, -2))
        assert window.total.text() == "01:40"
        window._position(400_000)
        assert window.total.text() == "00:00"
        window._duration(0)
        assert window.total.text() == "00:00"
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.text() == "00:00" and window.total.width() == 62
    finally:
        window.close()


def test_remaining_time_tracks_real_seek_and_clear(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths(paths)
    window.show()
    try:
        window.play(0)
        wait_until(lambda: window.player.media.duration() == 4000)
        window.player.media.pause()
        window.player.media.setPosition(2000)
        wait_until(lambda: window.total.text() == "00:02")
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.text() == "00:04"
        window._clear_playlist()
        assert window.total.text() == "00:00"
        window.add_paths(paths)
        window.play(1)
        wait_until(lambda: window.player.media.duration() == 4000)
        window.player.media.pause()
        window.player.media.setPosition(1000)
        wait_until(lambda: window.total.text() == "00:03")
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.text() == "00:04"
    finally:
        window.close()


def test_remaining_time_color_switch_keeps_waveform_geometry(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    try:
        window._duration(262_000)
        window._position(188_000)
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        qt_app.processEvents()
        wave_geometry = window.wave.geometry()
        label_geometry = window.total.geometry()
        original_color = window.total.palette().color(QPalette.ColorRole.WindowText)
        remaining_color = QColor(THEME_COLORS["danger"])
        for _ in range(5):
            QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
            qt_app.processEvents()
            assert window.total.text() == "01:14"
            assert window.total.palette().color(QPalette.ColorRole.WindowText) == remaining_color
            assert window.wave.geometry() == wave_geometry
            assert window.total.geometry() == label_geometry
            window._position(200_000)
            qt_app.processEvents()
            assert window.total.text() == "01:02"
            assert window.wave.geometry() == wave_geometry
            QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
            qt_app.processEvents()
            assert window.total.text() == "04:22"
            assert window.total.palette().color(QPalette.ColorRole.WindowText) == original_color
            assert window.wave.geometry() == wave_geometry
            assert window.total.geometry() == label_geometry
            window._position(188_000)
    finally:
        window.close()


def test_restart_and_new_track_default_to_remaining(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    paths = make_tracks(tmp_path)
    window = PlayerWindow(store)
    try:
        assert window.total.property("remainingTime") is True
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.property("remainingTime") is False
        window.add_paths(paths)
        window.volume.setValue(0)
        window.play(0)
        assert window.total.property("remainingTime") is True
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert window.total.property("remainingTime") is False
        window.play(1)
        assert window.total.property("remainingTime") is True
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
    finally:
        window.close()
    reopened = PlayerWindow(store)
    try:
        assert reopened.total.property("remainingTime") is True
        assert reopened.total.palette().color(QPalette.ColorRole.WindowText) == QColor(THEME_COLORS["danger"])
    finally:
        reopened.close()
