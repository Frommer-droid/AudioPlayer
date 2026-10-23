"""Проверки поведения очереди и направления перемотки."""
from app.core.playlist import Playlist, format_time, wheel_seek_position


def test_wheel_towards_moves_forward():
    assert wheel_seek_position(10000, 60000, -120) == 15000
    assert wheel_seek_position(10000, 60000, 120) == 5000


def test_natural_scroll_and_track_edges():
    assert wheel_seek_position(10000, 60000, 120, inverted=True) == 15000
    assert wheel_seek_position(58000, 60000, -120) == 60000
    assert wheel_seek_position(1000, 60000, 120) == 0
    assert wheel_seek_position(10000, 60000, -30) == 11250


def test_playlist_filters_deduplicates_and_preserves_current(tmp_path):
    first, second, ignored = [tmp_path / name for name in ("one.MP3", "two.wav", "text.txt")]
    for path in (first, second, ignored):
        path.touch()
    playlist = Playlist()
    assert playlist.add([first, first, ignored, second, tmp_path / "absent.mp3"]) == 2
    playlist.current = 1
    playlist.remove([0])
    assert playlist.paths == [second]
    assert playlist.current == 0
    playlist.remove([0])
    assert playlist.current == -1
    assert playlist.next_index() is None


def test_queue_end_and_repeat(tmp_path):
    playlist = Playlist()
    playlist.paths = [tmp_path / "one.mp3", tmp_path / "two.wav"]
    playlist.current = 1
    assert playlist.next_index() is None
    assert playlist.next_index(repeat=True) == 0
    assert playlist.next_index(-1) == 0
    assert playlist.next_index(shuffle=True) == 0


def test_time_format():
    assert format_time(0) == "00:00"
    assert format_time(75000) == "01:15"
    assert format_time(3600000) == "60:00"


def test_shuffle_finishes_cycle_unless_repeated(tmp_path):
    playlist = Playlist()
    playlist.paths = [tmp_path / "one.mp3", tmp_path / "two.wav"]
    playlist.current = 0
    assert playlist.next_index(shuffle=True) == 1
    playlist.current = 1
    assert playlist.next_index(shuffle=True) is None
    assert playlist.next_index(shuffle=True, repeat=True) == 0
