"""Неинтерактивная проверка frozen runtime, без показа окон и пользовательских данных."""
import json
import math
import struct
import tempfile
import time
import traceback
import wave
from pathlib import Path
from threading import Event


def run(report_path):
    report = {"ok": False}
    try:
        import av
        import numpy
        from PySide6.QtGui import QImage
        from PySide6.QtMultimedia import QAudioBufferOutput
        from PySide6.QtWidgets import QApplication

        from app.core.settings import ROOT, SettingsStore
        from app.services.duration import read_duration_ms
        from app.services.metadata import read_metadata
        from app.services.open_requests import read_request, write_request
        from app.services.player import PlayerService
        from app.services.single_instance import SingleInstance
        from app.services.waveform import calculate_peaks
        from app.ui.application_icon import application_icon
        from app.ui.main_window import PlayerWindow
        from app.ui.theme import apply_theme

        app = QApplication([])
        apply_theme(app)
        with tempfile.TemporaryDirectory(prefix="audioplayer-smoke-") as directory:
            folder = Path(directory)
            path = folder / "tone.wav"
            with wave.open(str(path), "wb") as stream:
                stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                stream.writeframes(struct.pack("<32000h", *[
                    int(10000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(32000)]))
            assert read_duration_ms(path) == 2000
            request = write_request([path], directory=folder / "requests")
            assert read_request(request, directory=folder / "requests") == [str(path)]
            assert read_metadata(path).sample_rate == 16000
            assert calculate_peaks(path, Event())
            assert not application_icon().isNull()
            instance = SingleInstance(folder / "instance")
            assert instance.start_or_forward([])
            instance.close()
            window = PlayerWindow(SettingsStore(folder / "settings.json"))
            window.tray.hide()
            assert window.brand_mark.isCheckable()
            window._add_playlist()
            window.add_paths([path])
            assert len(window.collection.playlists) == 2
            assert window.playlist.paths == [path]
            window.player.audio.setVolume(0)
            image = QImage(8, 8, QImage.Format.Format_RGB32)
            image.fill(0xff123456)
            assert image.save(str(folder / "folder.png"))
            window.open_paths([folder / "missing.wav", path])
            assert window.cover.image == image
            assert window.playlist.current == 0 and window.playlist.paths == [path]
            assert window.player.media.source().toLocalFile() == path.as_posix()
            assert window.total.property("remainingTime") is True and window.total.width() == 62
            window._toggle_remaining_time()
            assert window.total.property("remainingTime") is False
            window.play(0)
            assert window.total.property("remainingTime") is True
            second = folder / "alpha.wav"
            second.write_bytes(path.read_bytes())
            window.add_paths([second])
            window._sort_playlist(1)
            assert window.playlist.paths == [second, path] and window.playlist.current == 1
            assert window.table.item(0, 1).text() == "alpha"
            assert not window.table.horizontalHeader().isHidden()
            window.library.set_lyrics("Runtime lyrics")
            window.library.show_lyrics()
            assert window.library.pages.currentWidget() is window.library.lyrics_page
            assert not window.isVisible() and not window.library.isVisible()
            assert window.wheel_step.value() == 5
            window.close()
            window = PlayerWindow(SettingsStore(folder / "settings.json"))
            assert all(not playlist.paths for playlist in window.collection.playlists)
            assert window.player.media.source().isEmpty()
            assert window._dialog_directory() == str(folder)
            assert window.total.property("remainingTime") is True
            window.close()
            player = PlayerService()
            player.audio.setVolume(0)
            output = QAudioBufferOutput(player)
            player.media.setAudioBufferOutput(output)
            samples, errors = [], []
            output.audioBufferReceived.connect(lambda buffer: samples.append(buffer.sampleCount()))
            player.failed.connect(errors.append)
            player.open(path)
            deadline = time.monotonic() + 8
            while not samples and not errors and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            player.stop(reload=False)
            assert not errors, errors
            assert sum(samples) > 0
            report.update(ok=True, pcm_samples=sum(samples), root=str(ROOT),
                          av=av.__version__, numpy=numpy.__version__)
        app.quit()
    except BaseException:
        report["error"] = traceback.format_exc()
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
