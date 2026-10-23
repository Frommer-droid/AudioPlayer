"""Поиск скрывает строки, сохраняя очередь и исходные индексы действий."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_open_files import make_tracks
from tests.test_playback_modes import wait_until


def test_icon_toolbar_and_live_search_do_not_remove_hidden_tracks(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    before = {path: path.read_bytes() for path in paths}
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.add_paths(paths)
    window.show()
    window._show_playlist()
    panel = window.library
    try:
        buttons = (panel.add_files_button, panel.add_folder_button, panel.remove_button, panel.clear_button)
        assert len({(button.width(), button.height()) for button in buttons}) == 1
        for button in buttons:
            assert button.text() == "" and not button.icon().isNull()
            assert not button.toolTip() and button.accessibleName()
        assert panel.table.geometry().bottom() < panel.playlist_footer.y()
        positions = [widget.mapTo(panel, QPoint()).x() for widget in (panel.search, panel.count, *buttons)]
        assert positions == sorted(positions)
        assert all(button.parentWidget() is panel.playlist_footer for button in buttons)
        panel.playlist_footer.layout().activate()
        counter_width, search_width = panel.count.width(), panel.search.width()
        window.table.selectRow(0)
        panel.search.setFocus()
        QTest.keyClicks(panel.search, "  ExTrA  ")
        assert [window.table.isRowHidden(row) for row in range(3)] == [True, True, False]
        assert panel.count.text() == "Найдено: 1 / 3"
        assert not panel.remove_button.isEnabled()
        window._remove()
        assert window.playlist.paths == paths
        window.table.selectRow(2)
        QTest.keyClick(panel.search, Qt.Key.Key_Home)
        QTest.keyClick(panel.search, Qt.Key.Key_End)
        panel.search.setText("extra")
        panel.search.setCursorPosition(0)
        QTest.keyClick(panel.search, Qt.Key.Key_Delete)
        assert panel.search.text() == "xtra" and window.playlist.paths == paths
        assert window.playlist.current == -1
        panel.search.setText("not found")
        assert all(window.table.isRowHidden(row) for row in range(3))
        assert panel.count.text() == "Найдено: 0 / 3"
        panel.playlist_footer.layout().activate()
        assert (panel.count.width(), panel.search.width()) == (counter_width, search_width)
        panel.search.clear()
        assert not any(window.table.isRowHidden(row) for row in range(3))
        assert panel.count.text() == "Треков: 3"
        panel.playlist_footer.layout().activate()
        assert (panel.count.width(), panel.search.width()) == (counter_width, search_width)
        assert {path: path.read_bytes() for path in paths} == before
    finally:
        window.close()


def test_filtered_play_and_remove_keep_original_indices(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths(paths)
    window.show()
    window._show_playlist()
    panel = window.library
    try:
        panel.search.setText("extra")
        rect = window.table.visualItemRect(window.table.item(2, 1))
        QTest.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        QTest.mouseDClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        wait_until(lambda: window.playlist.current == 2)
        assert window.playlist.paths[window.playlist.current] == paths[2]
        assert panel.search.text() == "extra"
        assert [window.table.isRowHidden(row) for row in range(3)] == [True, True, False]
        QTest.mouseClick(panel.remove_button, Qt.MouseButton.LeftButton)
        assert window.playlist.paths == paths[:2]
        assert panel.count.text() == "Найдено: 0 / 2"
        assert all(path.is_file() for path in paths)
        window.add_paths([paths[2]])
        assert [window.table.isRowHidden(row) for row in range(3)] == [True, True, False]
        QTest.mouseClick(panel.clear_button, Qt.MouseButton.LeftButton)
        assert window.playlist.paths == []
        assert panel.count.text() == "Найдено: 0 / 0"
    finally:
        window.close()


def test_search_cyrillic_and_literal_punctuation(qt_app, tmp_path):
    paths = make_tracks(tmp_path)
    paths[0] = paths[0].rename(tmp_path / "Бодлер [Песня].wav")
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.add_paths(paths)
    try:
        window.library.search.setText("БОДЛЕР [")
        assert [window.table.isRowHidden(row) for row in range(3)] == [False, True, True]
        assert window.playlist.paths == paths
    finally:
        window.close()
