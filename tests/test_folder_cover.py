"""Folder artwork fallback, embedded priority and clearing between tracks."""
from pathlib import Path

import pytest
from mutagen.id3 import APIC
from mutagen.wave import WAVE
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.core.settings import SettingsStore
from app.services.cover_art import folder_cover
from app.ui.main_window import PlayerWindow
from tests.test_lyrics_tabs import tagged_wav


def image_file(path, color=Qt.GlobalColor.red):
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(color)
    assert image.save(str(path))
    return path.read_bytes()


@pytest.mark.parametrize("name", ["Обложка.PNG", "Folder.JpG", "front.webp", "image.bmp"])
def test_fallback_reads_common_images_without_writing(qt_app, tmp_path, name):
    path = tmp_path / name
    data = image_file(path)
    assert folder_cover(tmp_path / "трек.wav") == data
    assert path.read_bytes() == data


def test_named_priority_invalid_files_and_deterministic_fallback(qt_app, tmp_path, monkeypatch):
    track = tmp_path / "track.wav"
    custom = image_file(tmp_path / "Альбом.png")
    image_file(tmp_path / "Буклет.png")
    front = image_file(tmp_path / "Front.png")
    folder = image_file(tmp_path / "FOLDER.jpg")
    cover = image_file(tmp_path / "Cover.png")
    assert folder_cover(track) == cover
    (tmp_path / "Cover.png").write_bytes(b"broken image")
    assert folder_cover(track) == folder
    original_read = Path.read_bytes

    def unreadable(path):
        if path.name == "FOLDER.jpg":
            raise PermissionError("Fixture unreadable image")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    assert folder_cover(track) == front
    (tmp_path / "Front.png").write_bytes(b"")
    assert folder_cover(track) == custom
    assert folder_cover(tmp_path / "missing" / "track.wav") == b""


def test_playback_prefers_embedded_then_folder_and_clears_old_cover(qt_app, tmp_path):
    album = tmp_path / "Альбом с пробелами"
    empty = tmp_path / "Другой альбом"
    album.mkdir()
    empty.mkdir()
    cover = image_file(album / "folder.png", Qt.GlobalColor.blue)
    embedded = image_file(empty / "temporary.png", Qt.GlobalColor.red)
    (empty / "temporary.png").unlink()  # Fixture directory must have no artwork.
    tagged = tagged_wav(album / "tagged.wav")
    untagged = tagged_wav(album / "untagged.wav")
    blank = tagged_wav(empty / "blank.wav")
    tags = WAVE(tagged)
    tags.add_tags()
    tags.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=embedded))
    tags.save()
    originals = {path: path.read_bytes() for path in (tagged, untagged, blank, album / "folder.png")}
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    try:
        window.open_paths([tagged, untagged, blank])
        assert window.cover.image.pixelColor(0, 0) == Qt.GlobalColor.red
        window.play(1)
        assert window.cover.image == QImage.fromData(cover)
        window.play(2)
        assert window.cover.image.isNull()
        assert window.playlist.paths == [tagged, untagged, blank]
        assert all(path.read_bytes() == data for path, data in originals.items())
    finally:
        window.close()
