"""Independent browsing/playback and session-only tracks across restarts."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from app.core.playlist_collection import PlaylistCollection
from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow
from tests.test_lyrics_tabs import tagged_wav


def test_duration_opens_lyrics_and_icon_returns_to_playlist(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    panel = window.library
    try:
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert not panel.isVisible()
        panel.set_lyrics("Текст песни")
        QTest.mouseClick(window.total, Qt.MouseButton.RightButton)
        assert not panel.isVisible()
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert panel.isVisible()
        assert panel.pages.currentWidget() is panel.lyrics_page
        assert panel.tabs.count() == 1
        assert panel.lyrics_button.isChecked()
        assert panel.lyrics_font_controls.isVisible()
        assert panel.lyrics_button.geometry().right() < panel.close_button.x()
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert not panel.isVisible()
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert panel.isVisible() and panel.pages.currentWidget() is panel.lyrics_page
        QTest.mouseClick(panel.lyrics_button, Qt.MouseButton.LeftButton)
        assert panel.pages.currentIndex() == 0
        QTest.mouseClick(panel.lyrics_button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.tabs, Qt.MouseButton.LeftButton, pos=panel.tabs.tabRect(0).center())
        assert panel.pages.currentIndex() == 0
        panel.set_lyrics("")
        assert not panel.lyrics_button.isVisible()
        QTest.mouseClick(window.total, Qt.MouseButton.LeftButton)
        assert panel.pages.currentIndex() == 0
    finally:
        window.close()


def test_tabs_keep_playback_queue_and_isolate_edits(qt_app, tmp_path, monkeypatch):
    paths = [tagged_wav(tmp_path / f"track{i}.wav") for i in range(3)]
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window._show_playlist()
    opened = []
    monkeypatch.setattr(window.player, "open", opened.append)
    monkeypatch.setattr(window.wave_service, "open", lambda _path: None)
    try:
        window.add_paths(paths[:2])
        first = window.playlist
        window.play(0)
        window.library.search.setText("track0")
        QTest.mouseClick(window.library.add_playlist_button, Qt.MouseButton.LeftButton)
        assert window.library.tabs.currentIndex() == 1
        assert window.library.tabs.tabText(1) == "Плейлист 2"
        assert window.table.rowCount() == 0
        assert window.library.search.text() == ""
        second = window.playlist
        window.add_paths([paths[2]])
        assert first.paths == paths[:2] and second.paths == paths[2:]
        assert opened == paths[:1]
        window._set_repeat_mode("queue")
        window._ended()
        assert opened == paths[:2]  # Advance the original queue while viewing another.
        assert window.playlist is second and window._playing_playlist is first
        assert window.table.item(0, 1).text() == "track2"
        window._clear_playlist()
        assert first.paths == paths[:2] and first.current == 1
        window.library.tabs.setCurrentIndex(0)
        assert window.library.search.text() == "track0"
        window.library.search.clear()
        assert window.table.item(1, 0).text() == "▶"
        window.library.tabs.setCurrentIndex(1)
        window.add_paths([paths[2]])
        window.play(0)
        assert window._playing_playlist is second
        assert opened[-1] == paths[2]
    finally:
        window.close()


def test_tracks_are_session_only_across_five_restarts(qt_app, tmp_path):
    paths = [tagged_wav(tmp_path / f"persist{i}.wav") for i in range(3)]
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"playlist": [str(paths[0])]})
    window = PlayerWindow(store)
    assert window.playlist.paths == []
    window.add_paths(paths[:1])
    window.volume.setValue(37)
    window._add_playlist()
    window.add_paths(paths[1:])
    window._add_playlist()
    window.close()
    for _ in range(5):
        window = PlayerWindow(store)
        try:
            assert window.library.tabs.count() == 3
            assert window.library.tabs.currentIndex() == 2
            assert all(p.paths == [] and p.current == -1 for p in window.collection.playlists)
            assert [p.name for p in window.collection.playlists] == ["Плейлист", "Плейлист 2", "Плейлист 3"]
            assert window._playing_playlist is window.collection.playlists[2]
            assert window.volume.value() == 37
            assert window.player.media.source().isEmpty()
            assert window.player.media.playbackState().name == "StoppedState"
            window.volume.setValue(0)
            window.open_paths(paths[:1])
            window.add_paths(paths[1:])
            assert window.playlist.paths == paths
            window.volume.setValue(37)
        finally:
            window.close()
        saved = store.load()
        assert "playlist" not in saved and "playing_playlist" not in saved
        assert all(set(record) == {"name"} for record in saved["playlists"])


def test_collection_validates_saved_data_and_tracks_missing_files(tmp_path):
    paths = [tagged_wav(tmp_path / f"saved{i}.wav") for i in range(2)]
    data = {"playlists": [None, {"name": {}, "paths": [None, str(paths[0]), str(paths[1])], "current": 2},
                          {"name": "Второй", "paths": "wrong"}],
            "active_playlist": True, "playing_playlist": 999}
    library = PlaylistCollection(data)
    assert library.active == library.playing == 0
    assert len(library.playlists) == 2
    assert library.playlists[0].current == -1
    assert library.playlists[0].paths == []
    assert library.playlists[1].paths == []
    assert PlaylistCollection({"playlists": [None]}).playlists[0].name == "Плейлист"


def test_many_tabs_keep_header_actions_visible_at_minimum_width(qt_app, tmp_path):
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.show()
    window._show_playlist()
    panel = window.library
    try:
        for _ in range(24):
            window._add_playlist()
        panel.detach()
        panel.set_lyrics("Текст")
        panel.show_lyrics()
        panel.resize(panel.minimumSizeHint().width(), 300)
        qt_app.processEvents()
        controls = (panel.tabs, panel.add_playlist_button, panel.lyrics_button, panel.close_button)
        for widget in controls:
            assert widget.isVisible()
            assert widget.parentWidget().rect().contains(widget.geometry())
        for left, right in zip(controls, controls[1:]):
            assert left.geometry().right() < right.x()
        assert panel.tabs.usesScrollButtons()
        assert panel.tabs.currentIndex() == 24
        assert not panel.tabs.drawBase()
        font_controls = panel.lyrics_font_controls
        assert font_controls.parentWidget() is panel.lyrics_page
        assert panel.lyrics_page.rect().contains(font_controls.geometry())
        assert font_controls.geometry().right() >= panel.lyrics_page.width() - 4
        assert panel.lyrics_text.geometry().bottom() < font_controls.y()
        assert font_controls.geometry().bottom() >= panel.lyrics_page.height() - 4
    finally:
        window.close()


def test_right_click_closes_tabs_and_preserves_other_playlists(qt_app, tmp_path, monkeypatch):
    paths = [tagged_wav(tmp_path / f"close{i}.wav") for i in range(3)]
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.show()
    window._show_playlist()
    opened, stopped = [], []
    monkeypatch.setattr(window.player, "open", opened.append)
    monkeypatch.setattr(window.player, "stop", lambda **_kw: stopped.append(True))
    monkeypatch.setattr(window.wave_service, "open", lambda _path: None)
    try:
        window.add_paths(paths[:1])
        window.play(0)
        first = window.playlist
        window._add_playlist()
        window.add_paths(paths[1:2])
        window._add_playlist()
        window.add_paths(paths[2:])
        third = window.playlist
        tabs = window.library.tabs
        window.library.set_lyrics("Текст")
        window.library.show_lyrics()
        assert tabs.currentIndex() == 2 and window.library.lyrics_button.isChecked()
        assert tabs.property("lyricsActive") is None
        QTest.mouseClick(tabs, Qt.MouseButton.RightButton, pos=tabs.tabRect(1).center())
        assert window.collection.playlists == [first, third]
        assert window.playlist is third and window._playing_playlist is first
        assert tabs.currentIndex() == 1 and not stopped
        assert window.library.pages.currentIndex() == 1
        saved = PlaylistCollection(window.collection.serialize())
        assert [playlist.paths for playlist in saved.playlists] == [[], []]
        assert saved.active == saved.playing == 1
        QTest.mouseClick(tabs, Qt.MouseButton.RightButton, pos=tabs.tabRect(0).center())
        assert window.collection.playlists == [third] and stopped == [True]
        assert third.current == -1 and window.player.media.source().isEmpty()
        assert window.library.lyrics_text.toPlainText() == ""
        window._toggle()
        assert opened[-1] == paths[2]
        # A release outside the pressed tab must not close it.
        QTest.mousePress(tabs, Qt.MouseButton.RightButton, pos=tabs.tabRect(0).center())
        QTest.mouseRelease(tabs, Qt.MouseButton.RightButton, pos=QPoint(-1, -1))
        assert tabs.count() == 1 and window.playlist is third
        window._add_playlist()
        window._add_playlist()
        assert len({playlist.name for playlist in window.collection.playlists}) == 3
        while len(window.collection.playlists) > 1:
            window._close_playlist(0)
        window._close_playlist(0)
        assert tabs.count() == 1
        assert window.playlist.paths == [] and window.collection.active == window.collection.playing == 0
        assert paths[0].exists() and paths[1].exists() and paths[2].exists()
    finally:
        window.close()
    restored = PlayerWindow(store)
    try:
        assert restored.library.tabs.count() == 1 and restored.playlist.paths == []
    finally:
        restored.close()
