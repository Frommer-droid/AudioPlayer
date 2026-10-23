"""Named tabs with session-only track contents, without Qt."""
from app.core.playlist import Playlist


class PlaylistCollection:
    def __init__(self, settings):
        self.playlists = []
        records = settings.get("playlists")
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, dict):
                    continue
                name = record.get("name")
                self.add(name.strip() if isinstance(name, str) and name.strip() else None)
        if not self.playlists:
            self.add("Плейлист")
        self.active = self._index(settings.get("active_playlist"))
        self.playing = self.active

    def _index(self, value):
        return value if type(value) is int and 0 <= value < len(self.playlists) else 0

    def add(self, name=None):
        if name is None:
            number = len(self.playlists) + 1
            names = {playlist.name for playlist in self.playlists}
            while f"Плейлист {number}" in names:
                number += 1
            name = f"Плейлист {number}"
        playlist = Playlist(name)
        self.playlists.append(playlist)
        return playlist

    def serialize(self):
        return {
            "playlists": [{"name": playlist.name} for playlist in self.playlists],
            "active_playlist": self.active,
        }
