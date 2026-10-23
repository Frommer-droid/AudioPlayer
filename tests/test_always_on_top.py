"""Logo toggle changes real Windows topmost flags without drifting geometry."""
import ctypes
import sys
from ctypes import wintypes

import pytest
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_open_files import make_tracks
from tests.test_playback_modes import wait_until


class WindowEvents(QObject):
    def __init__(self):
        super().__init__()
        self.events = []

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Hide, QEvent.Type.Show, QEvent.Type.Move, QEvent.Type.Resize,
                            QEvent.Type.WinIdChange, QEvent.Type.ParentChange):
            self.events.append((watched, event.type()))
        return False


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows z-order regression")
@pytest.mark.parametrize("offset", [0, 8, -8])
def test_pin_at_taskbar_does_not_hide_recreate_or_move_windows(qt_app, tmp_path, offset):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    area = window.screen().availableGeometry()
    window.resize(min(900, area.width() - 40), window.height())
    window.move(area.left() + 20, area.bottom() + 1 - window.height() + offset)
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    windows = (window, window.library)
    originals = [(widget.geometry(), int(widget.winId())) for widget in windows]
    spy = WindowEvents()
    for widget in windows:
        widget.installEventFilter(spy)
    try:
        for _ in range(5):
            for enabled in (True, False):
                QTest.mouseClick(window.brand_mark, Qt.MouseButton.LeftButton)
                qt_app.processEvents()
                assert not spy.events, spy.events
                for widget, (geometry, handle) in zip(windows, originals):
                    assert widget.geometry() == geometry
                    assert int(widget.winId()) == handle
                    assert widget.isVisible()
                    assert_native_topmost(widget, enabled)
                assert window.library.docked
    finally:
        for widget in windows:
            widget.removeEventFilter(spy)
        window.close()


def test_pinning_remains_on_after_panel_show_and_tray_restore(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window._set_on_top(True)
    try:
        window._show_playlist()
        window._show_settings()
        qt_app.processEvents()
        for widget in (window, window.library, window.preferences):
            assert_native_topmost(widget, True)
        active = qt_app.activeWindow()
        window._set_on_top(False)
        window._set_on_top(True)
        qt_app.processEvents()
        assert qt_app.activeWindow() is active
        window.preferences.hide()
        window.showMinimized()
        qt_app.processEvents()
        window._set_on_top(False)
        assert window.isMinimized()
        window._set_on_top(True)
        window._restore_from_tray()
        qt_app.processEvents()
        assert window.isVisible() and not window.isMinimized()
        assert window.library.isVisible()
        assert_native_topmost(window, True)
        assert_native_topmost(window.library, True)
    finally:
        window.close()


def assert_native_topmost(window, enabled):
    if sys.platform == "win32":
        get_style = ctypes.windll.user32.GetWindowLongPtrW
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        assert bool(get_style(int(window.winId()), -20) & 0x8) == enabled


@pytest.mark.parametrize("detached", [False, True])
def test_logo_toggles_native_topmost_without_geometry_drift(qt_app, tmp_path, detached):
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.move(180, 100)
    window.resize(900, window.height())
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    if detached:
        window.library.detach()
        window.library.move(230, 300)
    geometry = window.geometry(), window.library.geometry()
    try:
        for _ in range(5):
            for enabled in (True, False):
                QTest.mouseClick(window.brand_mark, Qt.MouseButton.LeftButton)
                qt_app.processEvents()
                assert window.brand_mark.isChecked() == enabled
                assert window._always_on_top == enabled
                assert_native_topmost(window, enabled)
                assert_native_topmost(window.library, enabled)
                assert window.isVisible() and window.library.isVisible()
                assert (window.geometry(), window.library.geometry()) == geometry
                assert window.library.docked != detached
                image = window.brand_mark.grab().toImage()
                orange = any(image.pixelColor(x, y).red() > 160
                             and 60 < image.pixelColor(x, y).green() < 190
                             and image.pixelColor(x, y).blue() < 80
                             for x in range(image.width()) for y in range(image.height()))
                assert orange == enabled
        QTest.mouseClick(window.brand_mark, Qt.MouseButton.LeftButton)
    finally:
        window.close()
    restored = PlayerWindow(store)
    restored.show()
    qt_app.processEvents()
    try:
        assert restored.brand_mark.isChecked()
        assert_native_topmost(restored, True)
        assert restored.geometry() == geometry[0]
    finally:
        restored.close()


def test_pinned_window_stays_above_normal_window(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.move(180, 100)
    window.show()
    cover = QWidget()
    cover.setGeometry(window.geometry())
    try:
        window._set_on_top(True)
        cover.show()
        cover.raise_()
        qt_app.processEvents()
        point = window.mapToGlobal(window.rect().center())
        assert qt_app.widgetAt(point).window() is window
        window._set_on_top(False)
        cover.raise_()
        cover.activateWindow()
        qt_app.processEvents()
        assert qt_app.widgetAt(point).window() is cover
    finally:
        cover.close()
        window.close()


def test_logo_toggle_does_not_restart_playback(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths(paths)
    window.show()
    try:
        window.play(0)
        wait_until(lambda: window.player.media.position() > 100)
        position = window.player.media.position()
        source = window.player.media.source()
        sources = []
        window.player.media.sourceChanged.connect(sources.append)
        for _ in range(4):
            QTest.mouseClick(window.brand_mark, Qt.MouseButton.LeftButton)
            qt_app.processEvents()
            assert window.player.media.source() == source
            assert window.player.media.playbackState().name == "PlayingState"
            assert window.player.media.position() >= position
        assert not sources and window.playlist.current == 0
    finally:
        window.close()
