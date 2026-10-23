"""Сортировка заголовками сохраняет связь таблицы с очередью и файлами."""
import wave

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow


def click_header(window, column):
    header = window.table.horizontalHeader()
    point = QPoint(header.sectionViewportPosition(column) + header.sectionSize(column) // 2,
                   header.height() // 2)
    QTest.mouseClick(header.viewport(), Qt.MouseButton.LeftButton, pos=point)


@pytest.fixture
def sorting_window(qt_app, tmp_path):
    # Beta.mp3 intentionally has an unknown duration (WAV bytes with MP3 suffix).
    paths = [tmp_path / name for name in ("Zulu.wav", "alpha.wav", "Beta.mp3")]
    for path, seconds in zip(paths, (2, 1, 3)):
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x00" * (8000 * seconds))
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    window.add_paths(paths)
    window.show()
    window._show_playlist()
    qt_app.processEvents()
    yield window, paths
    window.close()


@pytest.mark.parametrize("column, indices", [(0, [0, 1, 2]), (1, [1, 2, 0]),
                                           (2, [2, 0, 1]), (3, [1, 0, 2])])
def test_header_toggles_queue_sort(sorting_window, column, indices):
    window, paths = sorting_window
    assert window.table.horizontalHeader().isVisible()
    click_header(window, column)
    assert window.playlist.paths == [paths[i] for i in indices]
    click_header(window, column)
    # Stable sorting preserves equal-format tracks' order.
    expected = [paths[i] for i in ([0, 1, 2] if column == 2 else indices[::-1])]
    assert window.playlist.paths == expected
    assert [window.table.item(i, 1).text() for i in range(3)] == [p.stem for p in expected]
    assert window.table.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


def test_sort_preserves_playing_file_selection_filter_and_removal(sorting_window, qt_app):
    window, paths = sorting_window
    window.play(0)
    source = window.player.media.source()
    window.table.selectRow(1)
    click_header(window, 1)
    assert window.playlist.paths[window.playlist.current] == paths[0]
    assert window.player.media.source() == source
    assert window.playlist.paths[window.table.selectedItems()[0].row()] == paths[1]
    window.library.search.setText("Beta")
    click_header(window, 3)
    visible = [i for i in range(3) if not window.table.isRowHidden(i)]
    assert [window.playlist.paths[i] for i in visible] == [paths[2]]
    window.table.selectRow(visible[0])
    window._remove()
    assert paths[2] not in window.playlist.paths and paths[2].exists()
    assert window.player.media.source() == source
    window.library.search.clear()
    click_header(window, 0)
    assert window.playlist.paths == paths[:2]
    window._advance(1)
    assert window.player.media.source().toLocalFile() == paths[1].as_posix()
    assert window.table.currentRow() == window.playlist.current


def test_sort_is_per_tab_and_applies_to_added_tracks(sorting_window):
    window, paths = sorting_window
    click_header(window, 1)
    original = window.playlist
    window._add_playlist()
    window.add_paths(paths[::-1])
    assert window.playlist.paths == paths[::-1]
    assert not window.table.horizontalHeader().isSortIndicatorShown()
    click_header(window, 0)
    click_header(window, 0)
    window.library.tabs.setCurrentIndex(0)
    assert window.playlist is original
    assert window.table.horizontalHeader().sortIndicatorSection() == 1
    window.playlist.remove([window.playlist.paths.index(paths[1])])
    window.add_paths([paths[1]])
    assert window.playlist.paths == [paths[1], paths[2], paths[0]]
    click_header(window, 0)
    assert window.playlist.paths == [paths[0], paths[2], paths[1]]


def test_duration_sort_uses_milliseconds_and_double_click_opens_visible_track(sorting_window, monkeypatch):
    window, paths = sorting_window
    values = {paths[0]: 100 * 60_000, paths[1]: 99 * 60_000, paths[2]: None}
    monkeypatch.setattr("app.ui.main_window.read_duration_ms", values.get)
    click_header(window, 3)
    assert window.playlist.paths == [paths[1], paths[0], paths[2]]
    assert window.table.item(0, 3).text() == "99:00"
    assert window.table.item(1, 3).text() == "100:00"
    item = window.table.item(1, 1)
    point = window.table.visualItemRect(item).center()
    QTest.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    QTest.mouseDClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert window.player.media.source().toLocalFile() == paths[0].as_posix()
    assert window.playlist.current == 1


@pytest.mark.parametrize("count", [104, 1004])
def test_number_width_fits_hundreds_and_numeric_sort(qt_app, tmp_path, count):
    paths = [tmp_path / f"Track {i}.mp3" for i in range(count)]
    for path in paths:
        path.touch()
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    try:
        window.add_paths(paths)
        window.show()
        window._show_playlist()
        qt_app.processEvents()
        for column in (0, 2, 3):
            header = window.table.horizontalHeader()
            assert header.sectionSize(column) >= header.sectionSizeHint(column)
        width = window.table.columnWidth(0)

        def assert_number_is_not_elided(row):
            table = window.table
            option = QStyleOptionViewItem()
            option.initFrom(table)
            option.font = table.font()
            option.widget = table
            index = table.model().index(row, 0)
            table.itemDelegate().initStyleOption(option, index)
            option.rect = table.visualRect(index)
            text_rect = table.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, option, table)
            margin = table.style().pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, option, table) + 1
            assert option.fontMetrics.elidedText(
                option.text, table.textElideMode(), text_rect.width() - 2 * margin) == option.text

        for row in (98, 99, 103, count - 1):
            assert_number_is_not_elided(row)
        click_header(window, 0)
        click_header(window, 0)
        assert window.table.item(0, 0).text() == str(count)
        assert window.table.item(count - 10, 0).text() == "10"
        assert window.table.item(count - 9, 0).text() == "9"
        assert_number_is_not_elided(0)
        window.play(0)
        qt_app.processEvents()
        assert window.table.item(0, 0).text() == "▶"
        assert window.table.columnWidth(0) >= width
        assert_number_is_not_elided(0)
        window.library.search.setText("Track 0")
        qt_app.processEvents()
        assert window.table.columnWidth(0) >= width
    finally:
        window.close()
