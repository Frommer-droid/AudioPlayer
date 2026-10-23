"""SVG-ресурсы, действия обложки и единая кнопка режимов повтора."""
import os

import pytest
from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.ui.icon_assets import ICON_FILES, create_renderer
from app.ui.main_window import PlayerWindow
from tests.test_runtime import wait_until


def test_all_svg_assets_render_in_theme_colors(qt_app):
    for symbol in ICON_FILES:
        for color in ("#E68C24", "#EEEEEE"):
            renderer = create_renderer(symbol, color)
            image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, 32, 32))
            painter.end()
            assert any(image.pixelColor(x, y).alpha() for x in range(32) for y in range(32)), symbol


def test_cover_only_left_click_opens_file(qt_app, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr("app.ui.main_window.QFileDialog.getOpenFileNames",
                        lambda *args: (opened.append(True) or [], ""))
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    try:
        QTest.mouseClick(window.cover, Qt.MouseButton.RightButton)
        assert not window.library.isVisible() and not opened
        QTest.mouseClick(window.cover, Qt.MouseButton.RightButton)
        assert not window.library.isVisible() and not opened
        QTest.mousePress(window.cover, Qt.MouseButton.RightButton)
        QTest.mouseRelease(window.cover, Qt.MouseButton.RightButton, pos=QPoint(-5, -5))
        assert not window.library.isVisible() and not opened
        QTest.mouseClick(window.cover, Qt.MouseButton.LeftButton)
        assert opened == [True] and not window.library.isVisible()
    finally:
        window.close()


def test_repeat_modes_cycle_and_restore_legacy_settings(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"repeat": True})
    window = PlayerWindow(store)
    window.show()
    try:
        assert window._repeat_mode == "playlist"
        for mode, checked, symbol in (("off", False, "repeat"), ("track", True, "repeat_one"),
                                      ("queue", True, "playlist_play"), ("playlist", True, "repeat"),
                                      ("off", False, "repeat"), ("track", True, "repeat_one")):
            QTest.mouseClick(window.repeat, Qt.MouseButton.LeftButton)
            assert window._repeat_mode == mode
            assert window.repeat.isChecked() == checked
            assert window.repeat.symbol == symbol
    finally:
        window.close()
    restored = PlayerWindow(store)
    assert restored._repeat_mode == "track"
    assert restored.repeat.symbol == "repeat_one"
    restored.close()


def test_repeat_track_keeps_current_source_on_end(qt_app, tmp_path):
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths([source])
    try:
        window.play(0)
        wait_until(lambda: window.player.media.position() > 100)
        before = window.player.media.source()
        window._set_repeat_mode("track")
        window._ended()
        assert window.player.media.source() == before
        assert window.playlist.current == 0
        assert window.player.media.position() < 100
        assert window.player.media.playbackState().name == "PlayingState"
    finally:
        window.close()
