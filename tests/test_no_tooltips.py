"""Hover help is disabled, including tooltips provided internally by Qt."""
from PySide6.QtCore import QEvent
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow


def test_no_hover_tooltips_in_player_or_panels(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window._show_playlist()
    window._show_settings()
    window.library.set_lyrics("Текст песни")
    window.library._set_lyrics_font_size(18)
    window._volume(40)
    window._set_on_top(True)
    window._cycle_repeat()
    window._notice_changed("Проверка")
    try:
        for widget in (window.play_button, window.repeat, window.brand_mark,
                       window.volume, window.track_info, window.wave, window.cover,
                       window.library.add_files_button, window.library.lyrics_font_increase):
            assert not widget.toolTip()
            assert widget.accessibleName() or widget.accessibleDescription()
        # Also suppress implicit/native widget help (e.g. a table viewport).
        for widget in (window.volume, window.table.viewport(), window.wheel_step):
            widget.setToolTip("Must never appear")
            point = widget.rect().center()
            event = QHelpEvent(QEvent.Type.ToolTip, point, widget.mapToGlobal(point))
            QApplication.sendEvent(widget, event)
            qt_app.processEvents()
            assert not QToolTip.isVisible()
            widget.setToolTip("")
        assert not window.tray.toolTip()
    finally:
        window.close()
