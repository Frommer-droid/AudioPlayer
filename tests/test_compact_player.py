"""Проверки компактного окна, метаданных и основных действий."""
import os
import shutil
from pathlib import Path

import pytest
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.services.metadata import TrackMetadata, read_metadata
from app.ui.main_window import PlayerWindow
from tests.test_runtime import wait_until


def test_tags_and_cover_are_read_without_changing_file(qt_app, tmp_path):
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    path = tmp_path / "tagged.mp3"
    shutil.copyfile(source, path)
    image_path = tmp_path / "cover.png"
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkRed)
    assert image.save(str(image_path))
    tags = ID3(path)
    tags.add(TIT2(encoding=3, text=["Тестовое название"]))
    tags.add(TPE1(encoding=3, text=["Исполнитель"]))
    tags.add(TALB(encoding=3, text=["Альбом"]))
    tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=image_path.read_bytes()))
    tags.save(path)
    before = path.read_bytes()
    data = read_metadata(path)
    assert data.title == "Тестовое название"
    assert data.artist == "Исполнитель"
    assert data.album == "Альбом"
    assert "44.1 kHz" in data.technical
    assert data.cover == image_path.read_bytes()
    assert path.read_bytes() == before
    assert data.heading == "Альбом · Исполнитель · Тестовое название"
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    try:
        window._show_metadata(path)
        assert window.track_title.text() == data.heading
        assert not window.track_title.toolTip()
        assert window.file_format.text() == "MP3"
        assert window.sample_rate.text() == "44.1 kHz"
        assert window.track_info.text() == f"{round(data.bitrate / 1000)} kbps"
        window._notice_changed("Временное сообщение")
        window._notice_changed("")
        assert window.track_info.text() == f"{round(data.bitrate / 1000)} kbps"
        for width in (860, 1100):
            window.resize(width, window.height())
            qt_app.processEvents()
            image = window.track_title.grab().toImage()
            columns = [x for x in range(image.width()) if any(
                image.pixelColor(x, y).lightness() > 160 for y in range(image.height()))]
            assert columns
            assert abs((min(columns) + max(columns)) / 2 - (image.width() - 1) / 2) <= 3
    finally:
        window.close()


def test_heading_omits_missing_tags():
    assert TrackMetadata(title="Файл").heading == "Файл"
    assert TrackMetadata(title="Песня", artist="Артист").heading == "Артист · Песня"
    assert TrackMetadata(title="Песня", artist=" ", album="Альбом").heading == "Альбом · Песня"


def test_compact_shell_and_separate_windows(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    try:
        assert window.height() == 147
        assert window.cover.width() == window.cover.height() == 60
        assert window.track_title.parent() == window.menu_button.parent()
        assert window.track_title.geometry().left() > window.menu_button.geometry().right()
        centers = [widget.mapTo(window, widget.rect().center()).y() for widget in (
            window.repeat, window.ab_button, window.previous_button,
            window.play_button, window.next_button, window.shuffle,
            window.mute_button, window.settings_button)]
        assert max(centers) - min(centers) <= 1
        assert 0 <= window.play_button.x() - window.previous_button.geometry().right() <= 10
        assert 0 <= window.next_button.x() - window.play_button.geometry().right() <= 10
        assert window.shuffle.geometry().right() < window.previous_button.x()
        def bounds(widget):
            origin = widget.mapTo(window, widget.rect().topLeft())
            return origin.x(), origin.x() + widget.width()
        assert bounds(window.mute_button)[0] - bounds(window.next_button)[1] == 20
        assert bounds(window.volume)[1] < bounds(window.settings_button)[0]
        row = (window.repeat, window.ab_button, window.shuffle, window.previous_button,
               window.play_button, window.next_button, window.mute_button, window.volume,
               window.settings_button)
        for width in (window.minimumWidth(), window.minimumWidth() + 1, 790, 791, 860, 1101, 1600):
            window.resize(width, window.height())
            qt_app.processEvents()
            title_center = window.track_title.mapTo(window, window.track_title.rect().center()).x()
            assert abs(title_center - window.rect().center().x()) <= 1
            block_left = bounds(window.repeat)[0]
            play_center = window.play_button.mapTo(window, window.play_button.rect().center()).x()
            wave_center = window.wave.mapTo(window, window.wave.rect().center()).x()
            assert abs(play_center - wave_center) <= 1
            assert bounds(window.track_info)[1] < block_left
            left_gap = block_left - bounds(window.track_info)[1]
            assert left_gap >= 8
            assert window.track_info.width() >= window.track_info.fontMetrics().horizontalAdvance("1536 kbps")
            assert window.volume.width() >= 125
            gaps = [bounds(right)[0] - bounds(left)[1] for left, right in zip(row, row[1:])]
            assert gaps == [8, 8, 20, 8, 8, 20, 8, 20]
        assert window.play_button.width() == 54
        assert all(widget.width() == 34 for widget in row
                   if widget not in (window.play_button, window.volume))
        assert window.width() / window.height() > 4
        assert not window.library.isVisible()
        assert not window.preferences.isVisible()
        assert not hasattr(window, "playlist_button")
        assert not hasattr(window, "open_button")
        QTest.mouseClick(window.elapsed, Qt.MouseButton.LeftButton)
        assert window.library.isVisible()
        qt_app.processEvents()
        header = window.table.horizontalHeader()
        for column in (2, 3):
            assert header.sectionSize(column) >= header.sectionSizeHint(column)
        QTest.mouseClick(window.elapsed, Qt.MouseButton.LeftButton)
        assert not window.library.isVisible()
        QTest.mouseClick(window.settings_button, Qt.MouseButton.LeftButton)
        assert window.preferences.isVisible()
        window.preferences.hide()
        QTest.mouseClick(window.mute_button, Qt.MouseButton.LeftButton)
        assert window.player.audio.isMuted()
        QTest.mouseClick(window.mute_button, Qt.MouseButton.LeftButton)
        assert not window.player.audio.isMuted()
    finally:
        window.close()


@pytest.mark.parametrize("edge", ["left", "right"])
def test_edge_drag_and_five_restarts_preserve_width_and_position(qt_app, tmp_path, edge):
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.move(240, 180)
    window.show()
    qt_app.processEvents()
    try:
        start = window.geometry()
        grip = getattr(window, f"_{edge}_grip")
        assert window.childAt(grip.geometry().center()) is grip
        point = grip.rect().center()
        delta = -130 if edge == "left" else 130
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + QPoint(delta, 0))
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        assert window.width() == start.width() + 130
        assert window.height() == start.height()
        assert window.x() == start.x() + (delta if edge == "left" else 0)
        point = grip.rect().center()
        shrink_delta = 200 if edge == "left" else -200
        QTest.mousePress(grip, Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseMove(grip, point + QPoint(shrink_delta, 0))
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, pos=grip.rect().center())
        qt_app.processEvents()
        assert window.width() == start.width() - 70
        assert window.width() < 860
        settings_right = window.settings_button.mapTo(window, window.settings_button.rect().topRight()).x()
        assert settings_right < window.width()
        expected = window.geometry()
    finally:
        window.close()
    for _ in range(5):
        window = PlayerWindow(store)
        window.show()
        qt_app.processEvents()
        try:
            assert window.geometry() == expected
        finally:
            window.close()


def test_visible_text_and_icons_have_equal_outer_gaps(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()

    def painted_bounds(widget):
        image = widget.grab().toImage()
        columns = [x for x in range(image.width()) if any(
            image.pixelColor(x, y).lightness() > 110 for y in range(image.height()))]
        assert columns
        origin = widget.mapTo(window, widget.rect().topLeft()).x()
        scale = image.devicePixelRatio()
        return origin + min(columns) / scale, origin + (max(columns) + 1) / scale

    try:
        for fmt, rate, bitrate in (("MP3", "48 kHz", "320 kbps"),
                                   ("WAV", "192 kHz", "9216 kbps"),
                                   ("FLAC", "44.1 kHz", "860 kbps")):
            window.file_format.setText(fmt)
            window.sample_rate.setText(rate)
            window.track_info.setText(bitrate)
            for width in (790, 1100, 1601):
                window.resize(width, window.height())
                qt_app.processEvents()
                text_right = max(painted_bounds(label)[1] for label in (
                    window.file_format, window.sample_rate, window.track_info))
                left_gap = painted_bounds(window.repeat)[0] - text_right
                right_gap = window.width() - painted_bounds(window.settings_button)[1]
                assert abs(left_gap - right_gap) <= 3
                assert abs(window.play_button.geometry().center().x()
                           - window.wave.geometry().center().x()) <= 1
    finally:
        window.close()


def test_compact_migration_only_happens_once(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    first = PlayerWindow(store)
    first.resize(1020, 147)
    first.move(180, 120)
    first.show()
    QTest.qWait(50)
    geometry = (first.pos().x(), first.pos().y(), first.width(), first.height())
    first.close()
    assert store.load()["window"]["layout_version"] == 2
    second = PlayerWindow(store)
    second.show()
    QTest.qWait(50)
    assert (second.pos().x(), second.pos().y(), second.width(), second.height()) == geometry
    second.close()


def test_play_pause_and_ab_controls(qt_app, tmp_path):
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.add_paths([Path(source)])
    window.volume.setValue(0)
    window.show()
    try:
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: window.player.media.duration() > 0)
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        assert window.player.media.playbackState().name == "PausedState"
        assert window.play_button.symbol == "play"
        window.player.media.setPosition(500)
        QTest.mouseClick(window.ab_button, Qt.MouseButton.LeftButton)
        window.player.media.setPosition(1500)
        QTest.mouseClick(window.ab_button, Qt.MouseButton.LeftButton)
        assert window._ab_start == 500
        assert window._ab_end == 1500
        window.player.media.setPosition(1600)
        wait_until(lambda: window.player.media.position() == 500)
        QTest.mouseClick(window.ab_button, Qt.MouseButton.LeftButton)
        assert window._ab_start is None
        assert not window.ab_button.isChecked()
    finally:
        window.close()


def test_previous_session_track_does_not_restore_metadata_or_waveform(qt_app, tmp_path):
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"playlist": [source]})
    window = PlayerWindow(store)
    window.show()
    try:
        assert window.player.media.playbackState().name == "StoppedState"
        assert not window.wave.peaks and window.wave.duration == 0
        assert window.player.media.source().isEmpty()
        assert window.cover.isVisible()
        assert window.track_title.text() == "Откройте музыку"
    finally:
        window.close()


def test_round_button_left_toggle_right_stop(qt_app, tmp_path):
    source = os.environ.get("AUDIOPLAYER_MP3_FIXTURE")
    if not source:
        pytest.skip("Задайте AUDIOPLAYER_MP3_FIXTURE")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.add_paths([source])
    window.volume.setValue(0)
    window.show()
    clicks = []
    window.play_button.clicked.connect(lambda: clicks.append(True))
    try:
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: window.player.media.position() > 150)
        assert window.play_button.symbol == "pause_circle"
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        assert window.player.media.playbackState().name == "PausedState"
        assert window.play_button.symbol == "play"
        paused_position = window.player.media.position()
        QTest.qWait(80)
        assert window.player.media.position() == paused_position
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: window.player.media.position() > paused_position)
        assert window.play_button.symbol == "pause_circle"
        click_count = len(clicks)
        QTest.mouseClick(window.play_button, Qt.MouseButton.RightButton)
        wait_until(lambda: window.player.media.playbackState().name == "StoppedState")
        assert window.player.media.playbackState().name == "StoppedState"
        assert window.player.media.position() == 0
        assert window.play_button.symbol == "play"
        assert len(clicks) == click_count
        QTest.qWait(80)
        assert window.player.media.playbackState().name == "StoppedState"
        QTest.mouseClick(window.play_button, Qt.MouseButton.LeftButton)
        wait_until(lambda: window.player.media.position() > 100)
        window.player.media.pause()
        assert window.play_button.symbol == "play"
    finally:
        window.close()
