"""Плейлист открывается продолжением плеера и может быть отстыкован."""
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_runtime import wait_until


@pytest.mark.parametrize("name", ["top", "bottom", "left", "right",
                                  "top_left", "top_right", "bottom_left", "bottom_right"])
def test_all_playlist_edges_and_corners_resize(qt_app, tmp_path, name):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.move(160, 120)
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    panel = window.library
    try:
        assert not panel.isSizeGripEnabled()
        original = panel.geometry()
        grip = panel._resize_grips[name]
        assert panel.childAt(grip.geometry().center()) is grip
        left, right = "left" in name, "right" in name
        top, bottom = "top" in name, "bottom" in name
        point = grip.rect().center()
        delta = QPoint(-40 if left else 40 if right else 0, -35 if top else 35 if bottom else 0)
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + delta)
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        assert panel.width() == original.width() + (40 if left or right else 0)
        assert panel.height() == original.height() + (35 if top or bottom else 0)
        assert panel.geometry().right() == original.right() if left else panel.x() == original.x()
        assert panel.geometry().bottom() == original.bottom() if top else panel.y() == original.y()
        assert panel.docked == (name == "bottom")
        point = grip.rect().center()
        delta = QPoint(2000 if left else -2000 if right else 0, 2000 if top else -2000 if bottom else 0)
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + delta)
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        if left or right:
            assert panel.width() == panel.minimumWidth()
        if top or bottom:
            assert panel.height() == panel.minimumHeight()
    finally:
        window.close()


def test_playlist_border_is_visible_near_bottom_right(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    try:
        panel = window.library
        image = panel.grab().toImage()
        scale = image.devicePixelRatio()

        def orange(x, y):
            color = image.pixelColor(x, y)
            return color.red() > 100 and color.red() > 2 * color.blue() and color.green() > color.blue()

        margin = round(12 * scale)
        for x in range(image.width() - round(60 * scale), image.width() - margin):
            assert any(orange(x, y) for y in range(image.height() - 3, image.height()))
        for y in range(image.height() - round(60 * scale), image.height() - margin):
            assert any(orange(x, y) for x in range(image.width() - 3, image.width()))
    finally:
        window.close()


@pytest.mark.parametrize("edge", ["top", "bottom"])
def test_playlist_height_drag_preserves_opposite_edge_and_minimum(qt_app, tmp_path, edge):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.move(100, 80)
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    panel = window.library
    try:
        original = panel.geometry()
        grip = getattr(panel, f"_{edge}_grip")
        assert panel.childAt(grip.geometry().center()) is grip
        point = grip.rect().center()
        delta = 70 if edge == "top" else -70
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + QPoint(0, delta))
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        assert panel.height() == original.height() - 70
        assert panel.width() == original.width()
        assert panel.docked == (edge == "bottom")
        if edge == "top":
            assert panel.geometry().bottom() == original.bottom()
        else:
            assert_docked(window)
        point = grip.rect().center()
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + QPoint(0, 1000 if edge == "top" else -1000))
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        assert panel.height() == panel.minimumHeight()
        if edge == "bottom":
            assert_docked(window)
    finally:
        window.close()


def assert_docked(window):
    player, playlist = window.frameGeometry(), window.library.frameGeometry()
    assert window.library.isVisible() and window.library.docked
    assert playlist.left() == player.left()
    assert playlist.top() == player.bottom() + 1
    assert playlist.width() == player.width()
    assert window.centralWidget().property("playlistAttached") is True


def test_open_follow_move_resize_detach_and_reopen(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.move(100, 80)
    window.show()
    try:
        QTest.mouseClick(window.elapsed, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert_docked(window)
        window.move(170, 110)
        window.resize(1100, window.height())
        qt_app.processEvents()
        assert_docked(window)
        height = window.library.height()
        window.library.resize(window.width(), height + 50)
        qt_app.processEvents()
        assert_docked(window)
        window.library.move(window.library.pos() + QPoint(70, 35))
        qt_app.processEvents()
        assert not window.library.docked
        detached = window.library.frameGeometry()
        window.move(200, 140)
        window.resize(1000, window.height())
        qt_app.processEvents()
        assert window.library.frameGeometry() == detached
        assert window.centralWidget().property("playlistAttached") is False
        QTest.mouseClick(window.elapsed, Qt.MouseButton.LeftButton)
        assert not window.library.isVisible()
        QTest.mouseClick(window.elapsed, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert_docked(window)
        assert window.library.height() == height + 50
    finally:
        window.close()


def test_playlist_hides_and_restores_with_player(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.move(100, 80)
    window.show()
    try:
        window._show_playlist()
        qt_app.processEvents()
        assert_docked(window)
        window.hide()
        qt_app.processEvents()
        assert not window.library.isVisible()
        window.show()
        wait_until(window.library.isVisible)
        assert_docked(window)
        window.showMinimized()
        wait_until(lambda: not window.library.isVisible())
        window.showNormal()
        wait_until(window.library.isVisible)
        assert_docked(window)
        window.library.close()
        assert not window.library.isVisible()
        window.hide()
        window.show()
        qt_app.processEvents()
        assert not window.library.isVisible()
        assert window.centralWidget().property("playlistAttached") is False
        window._show_playlist()
        qt_app.processEvents()
        assert_docked(window)
    finally:
        window.close()
    assert not window.library.isVisible()
