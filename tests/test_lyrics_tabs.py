"""Embedded lyrics: реальные ID3/WAV и видимость/содержимое вкладки."""
import wave
from types import SimpleNamespace

import pytest
from mutagen._vorbis import VCommentDict
from mutagen.apev2 import APEv2
from mutagen.asf import ASFTags
from mutagen.id3 import ID3, SYLT, USLT
from mutagen.mp4 import MP4Tags
from mutagen.wave import WAVE
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.settings import SettingsStore
from app.services.metadata import read_metadata
from app.ui.controls import IconButton
from app.ui.main_window import PlayerWindow


def tagged_wav(path, lyrics=None):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 1600)
    if lyrics is not None:
        audio = WAVE(path)
        audio.add_tags()
        audio.tags.add(USLT(encoding=3, lang="rus", desc="", text=lyrics))
        audio.save()
    return path


@pytest.mark.parametrize("kind", ["mp4", "vorbis", "ape", "asf", "sylt"])
def test_lyrics_tag_formats_are_read_without_writing(tmp_path, monkeypatch, kind):
    text = "Первая строка\n\nВторая строка"
    if kind == "mp4":
        tags = MP4Tags()
        tags["\xa9lyr"] = [text]
    elif kind == "vorbis":
        tags = VCommentDict()
        tags["LYRICS"] = [text]
    elif kind == "ape":
        tags = APEv2()
        tags["Lyrics"] = text
    elif kind == "asf":
        tags = ASFTags()
        tags["WM/Lyrics"] = [text]
    else:
        tags = ID3()
        tags.add(SYLT(encoding=3, lang="rus", format=2, type=1,
                      text=[("Первая строка\n\n", 0), ("Вторая строка", 1000)]))
    audio = SimpleNamespace(tags=tags, info=SimpleNamespace(sample_rate=16000, bitrate=256000, channels=1))
    monkeypatch.setattr("app.services.metadata.mutagen.File", lambda _path: audio)
    path = tmp_path / "track.wav"
    path.write_bytes(b"unchanged")
    assert read_metadata(path).lyrics == text
    assert path.read_bytes() == b"unchanged"


def test_lyrics_tab_follows_real_track_tags_and_clear(qt_app, tmp_path):
    text = "<b>Текст из тега</b>\n\nВторая строфа"
    with_lyrics = tagged_wav(tmp_path / "lyrics.wav", text)
    without = tagged_wav(tmp_path / "instrumental.wav")
    empty = tagged_wav(tmp_path / "empty.wav", " \n\t ")
    original = with_lyrics.read_bytes()
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"playlist": [str(with_lyrics), str(without)]})
    window = PlayerWindow(store)
    window.add_paths([with_lyrics, without])
    window.playlist.current = 0
    window._show_metadata(with_lyrics)
    window.show()
    window._show_playlist()
    panel = window.library
    try:
        assert panel.tabs.currentIndex() == 0
        assert panel.tabs.tabText(0) == "Плейлист"
        assert panel.tabs.count() == 1
        assert panel.lyrics_button.accessibleName() == "Текст песни"
        assert panel.lyrics_button.isVisible()
        assert panel.lyrics_text.toPlainText() == text
        assert panel.lyrics_text.isReadOnly()
        assert window.player.media.playbackState().name == "StoppedState"
        header = window.track_title.parent()
        assert not any(button.symbol == "max" for button in header.findChildren(IconButton))
        QTest.mouseClick(panel.lyrics_button, Qt.MouseButton.LeftButton)
        assert panel.pages.currentWidget() is panel.lyrics_page
        assert panel.lyrics_text.isVisible() and not panel.table.isVisible()
        window._show_metadata(without)
        assert not panel.lyrics_button.isVisible()
        assert panel.tabs.currentIndex() == 0
        assert panel.table.isVisible()
        assert panel.lyrics_text.toPlainText() == ""
        window._show_metadata(empty)
        assert not panel.lyrics_button.isVisible()
        window._show_metadata(with_lyrics)
        assert panel.lyrics_button.isVisible()
        window._clear_playlist()
        assert not panel.lyrics_button.isVisible()
        assert with_lyrics.read_bytes() == original
    finally:
        window.close()


def test_lyrics_font_buttons_resize_text_and_persist(qt_app, tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.show()
    panel = window.library
    text = "Текст песни\n\nВторая строфа"
    panel.set_lyrics(text)
    window._show_playlist()
    try:
        assert not panel.lyrics_font_controls.isVisible()
        panel.show_lyrics()
        qt_app.processEvents()
        assert panel.lyrics_font_controls.isVisible()
        before = panel.lyrics_text.cursorRect().height()
        playlist_font = panel.table.font()
        for _ in range(3):
            QTest.mouseClick(panel.lyrics_font_increase, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert panel.lyrics_font_size == 17
        assert panel.lyrics_text.cursorRect().height() > before
        assert panel.lyrics_text.toPlainText() == text
        assert panel.table.font() == playlist_font
        QTest.mouseClick(panel.lyrics_font_decrease, Qt.MouseButton.LeftButton)
        assert panel.lyrics_font_size == 16
        panel.show_playlist()
        assert not panel.lyrics_font_controls.isVisible()
        panel.show_lyrics()
        panel.set_lyrics("")
        assert not panel.lyrics_font_controls.isVisible()
        panel.set_lyrics(text)
        assert panel.lyrics_font_size == 16
    finally:
        window.close()
    restored = PlayerWindow(store)
    try:
        assert restored.library.lyrics_font_size == 16
        assert restored.library.lyrics_text.font().pixelSize() == 16
        assert restored.library.lyrics_text.document().defaultFont().pixelSize() == 16
    finally:
        restored.close()


@pytest.mark.parametrize("value,expected", [(None, 14), ({}, 14), (True, 14), ("bad", 14),
                                           (-100, 10), (1000, 32)])
def test_lyrics_font_saved_size_is_validated_and_limited(qt_app, tmp_path, value, expected):
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"lyrics_font_size": value})
    window = PlayerWindow(store)
    try:
        panel = window.library
        assert panel.lyrics_font_size == expected
        assert panel.lyrics_font_decrease.isEnabled() == (expected > 10)
        assert panel.lyrics_font_increase.isEnabled() == (expected < 32)
    finally:
        window.close()
