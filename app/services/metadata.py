"""Чтение тегов и обложки без изменения аудиофайла."""
import base64
from dataclasses import dataclass
from pathlib import Path

import av
import mutagen
from mutagen.flac import Picture


def _tag_text(tags, keys):
    for key in keys:
        try:
            value = tags.get(key)
        except ValueError:
            # Vorbis comments reject non-ASCII MP4 keys even on read.
            continue
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _cover(audio, tags):
    pictures = getattr(audio, "pictures", [])
    if pictures:
        return next((p for p in pictures if p.type == 3), pictures[0]).data
    covers = tags.getall("APIC") if hasattr(tags, "getall") else []
    if covers:
        return next((p for p in covers if p.type == 3), covers[0]).data
    for value in tags.get("covr", []):
        return bytes(value)
    for value in tags.get("metadata_block_picture", []):
        try:
            return Picture(base64.b64decode(value)).data
        except (ValueError, TypeError, mutagen.MutagenError):
            continue
    value = tags.get("Cover Art (Front)")
    if value is not None:
        return bytes(value).split(b"\0", 1)[-1]
    return b""


def _lyrics(tags):
    if hasattr(tags, "getall"):
        for frame in tags.getall("USLT"):
            if isinstance(frame.text, str) and frame.text.strip():
                return frame.text.strip()
        for frame in tags.getall("SYLT"):
            text = "".join(part for part, _timestamp in frame.text).strip()
            if text:
                return text
        for frame in tags.getall("TXXX"):
            if frame.desc.casefold() in ("lyrics", "unsyncedlyrics"):
                text = "\n".join(frame.text).strip()
                if text:
                    return text
    return _tag_text(tags, ("\xa9lyr", "lyrics", "unsyncedlyrics", "LYRICS", "UNSYNCEDLYRICS",
                            "Lyrics", "WM/Lyrics"))


def _native_metadata(path, result):
    """AIFF NAME/AUTH и сведения потока, которых нет в Mutagen StreamInfo."""
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                return
            stream = container.streams.audio[0]
            tags = {**container.metadata, **stream.metadata}
            if not result.lyrics:
                result.lyrics = _lyrics(tags)
            for attribute in ("title", "artist", "album"):
                if (attribute == "title" and result.title != path.stem) or (
                        attribute != "title" and getattr(result, attribute)):
                    continue
                text = _tag_text(tags, (attribute,))
                if text:
                    setattr(result, attribute, text)
            result.sample_rate = result.sample_rate or stream.codec_context.sample_rate or 0
            result.bitrate = result.bitrate or stream.codec_context.bit_rate or 0
    except (OSError, ValueError, av.FFmpegError):
        pass


@dataclass
class TrackMetadata:
    title: str
    artist: str = ""
    album: str = ""
    technical: str = ""
    cover: bytes = b""
    file_format: str = ""
    sample_rate: int = 0
    bitrate: int = 0
    lyrics: str = ""

    @property
    def heading(self):
        return " · ".join(value.strip() for value in (self.album, self.artist, self.title) if value.strip())


def read_metadata(path: Path) -> TrackMetadata:
    extension = path.suffix[1:].upper()
    result = TrackMetadata(title=path.stem, technical=extension, file_format=extension)
    try:
        audio = mutagen.File(path)
        if audio is None:
            _native_metadata(path, result)
            return result
        tags = audio.tags
        if tags is not None:
            for attribute, keys in (
                ("title", ("TIT2", "title", "\xa9nam", "Title")),
                ("artist", ("TPE1", "artist", "\xa9ART", "Author")),
                ("album", ("TALB", "album", "\xa9alb", "WM/AlbumTitle")),
            ):
                text = _tag_text(tags, keys)
                if text:
                    setattr(result, attribute, text)
            result.cover = _cover(audio, tags)
            result.lyrics = _lyrics(tags)
        info = audio.info
        details = [path.suffix[1:].upper()]
        sample_rate = getattr(info, "sample_rate", 0)
        bitrate = getattr(info, "bitrate", 0)
        channels = getattr(info, "channels", 0)
        result.sample_rate = sample_rate
        result.bitrate = bitrate
        if not sample_rate or path.suffix.lower() in (".aif", ".aiff"):
            _native_metadata(path, result)
            sample_rate, bitrate = result.sample_rate, result.bitrate
        if sample_rate:
            details.append(f"{sample_rate / 1000:g} kHz")
        if bitrate:
            details.append(f"{round(bitrate / 1000)} kbps")
        if channels:
            details.append({1: "Mono", 2: "Stereo"}.get(channels, f"{channels} ch"))
        result.technical = ", ".join(details)
    except (OSError, ValueError, mutagen.MutagenError):
        pass
    return result
