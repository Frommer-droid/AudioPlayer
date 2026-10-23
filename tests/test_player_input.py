"""Колесо по области указателя и неподвижный таймлайн при изменении цифр."""
import wave

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_playback_modes import wait_until


def wheel(widget, delta=120, *, inverted=False, pixels=0):
    local = widget.rect().center()
    event = QWheelEvent(QPointF(local), QPointF(widget.mapToGlobal(local)),
                        QPoint(0, pixels), QPoint(0, delta), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, inverted)
    QApplication.sendEvent(widget, event)


def test_wheel_seeks_only_over_waveform_and_changes_volume_elsewhere(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window.wave.duration, window.wave.position = 60000, 10000
    seeks = []
    window.wave.seek.connect(seeks.append)
    try:
        window.volume.setValue(50)
        window.volume.setFocus()
        wheel(window.wave, -120)
        assert seeks == [15000]
        assert window.volume.value() == 50
        window.wave.setFocus()
        for widget in (window, window.cover, window.track_title, window.file_format,
                       window.play_button, window.volume, window.elapsed, window.total,
                       window.settings_button):
            window.volume.setValue(50)
            wheel(widget)
            assert window.volume.value() == 45
            wheel(widget, -120)
            assert window.volume.value() == 50
        assert seeks == [15000]
        wheel(window.volume, 60)
        assert window.volume.value() == 50
        wheel(window.volume, 60)
        assert window.volume.value() == 45
        wheel(window.volume, inverted=True)
        assert window.volume.value() == 50
        wheel(window.volume, 0, pixels=20)
        wheel(window.volume, 0, pixels=20)
        assert window.volume.value() == 45
        window.volume.setValue(98)
        wheel(window.cover, -120)
        assert window.volume.value() == 100
        window.volume.setValue(0)
        wheel(window.cover)
        assert window.volume.value() == 0
        window.preferences.show()
        before = window.wheel_step.value()
        wheel(window.wheel_step)
        assert window.wheel_step.value() > before
        assert window.volume.value() == 0
    finally:
        window.close()


def test_active_player_hotkeys_work_over_focused_controls(qt_app, tmp_path):
    paths = []
    for index in range(2):
        path = tmp_path / f"keys{index}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b"\0\0" * 320000)
        paths.append(path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window.activateWindow()
    window.volume.setValue(0)
    window.add_paths(paths)
    try:
        wait_until(lambda: QApplication.activeWindow() is window)
        window.play(0)
        wait_until(lambda: window.player.media.duration() == 20000)
        window.player.media.pause()
        wait_until(lambda: window.player.media.playbackState().name == "PausedState")
        window.player.media.setPosition(4000)
        wait_until(lambda: window.player.media.position() == 4000)
        window.wheel_step.setValue(12)
        window.volume.setFocus()
        QTest.keyClick(window.volume, Qt.Key.Key_Right)
        wait_until(lambda: window.player.media.position() == 9000)
        assert window.volume.value() == 0
        QTest.keyClick(window.volume, Qt.Key.Key_Left)
        wait_until(lambda: window.player.media.position() == 4000)
        QTest.keyClick(window.volume, Qt.Key.Key_Left)
        wait_until(lambda: window.player.media.position() == 0)
        window.wave.setFocus()
        QTest.keyClick(window.wave, Qt.Key.Key_End)
        wait_until(lambda: window.playlist.current == 1)
        QTest.keyClick(window.wave, Qt.Key.Key_Home)
        wait_until(lambda: window.playlist.current == 0)
        wait_until(lambda: window.player.media.playbackState().name == "PlayingState")
        clicks = []
        window.play_button.clicked.connect(lambda: clicks.append(True))
        window.play_button.setFocus()
        QTest.keyClick(window.play_button, Qt.Key.Key_Space)
        wait_until(lambda: window.player.media.playbackState().name == "PausedState")
        QTest.keyClick(window.play_button, Qt.Key.Key_Space)
        wait_until(lambda: window.player.media.playbackState().name == "PlayingState")
        assert not clicks
        window._show_settings()
        wait_until(lambda: QApplication.activeWindow() is window.preferences)
        before = window.wheel_step.value()
        QTest.keyClick(window.wheel_step, Qt.Key.Key_Home)
        assert window.playlist.current == 0
        assert window.wheel_step.value() == before
    finally:
        window.close()


def test_time_labels_share_row_and_never_move_waveform(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    try:
        qt_app.processEvents()
        geometry = window.wave.geometry()
        assert window.elapsed.width() == window.total.width() == 62
        assert window.elapsed.font().pixelSize() == window.total.font().pixelSize() == 20
        assert window.elapsed.geometry().right() < geometry.left()
        assert window.total.geometry().left() > geometry.right()
        assert geometry.left() - window.elapsed.geometry().right() - 1 == 3
        assert window.total.geometry().left() - geometry.right() - 1 == 3
        centers = [widget.geometry().center().y() for widget in (window.elapsed, window.wave, window.total)]
        assert max(centers) - min(centers) <= 1
        for seconds in (0, 9, 59, 60, 3599, 3600, 5998):
            window._position(seconds * 1000)
            window._duration((seconds + 1) * 1000)
            qt_app.processEvents()
            assert window.wave.geometry() == geometry
            for label in (window.elapsed, window.total):
                assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width()
        window._duration(360000000)
        qt_app.processEvents()
        assert window.wave.geometry() == geometry
        assert not window.total.toolTip()
        window.grab().save(str(tmp_path / "inline-timeline.png"))
    finally:
        window.close()
