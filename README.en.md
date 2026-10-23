<p align="center"><img src="app/ui/assets/audioplayer.png" width="104" alt="AudioPlayer"></p>
<h1 align="center">AudioPlayer</h1>
<p align="center">A compact Windows music player with a waveform timeline.</p>
<p align="center"><a href="README.md">Русский</a> · <a href="https://github.com/Frommer-droid/AudioPlayer/releases/latest">Download</a></p>

![Player window](docs/release-player.png)

Play local music, view artwork and tags, and seek directly on the waveform.
The interface uses a graphite and orange palette. The current interface and installer are in Russian.

## Install

Download the installer from the [latest release](https://github.com/Frommer-droid/AudioPlayer/releases/latest),
install and start AudioPlayer. Requires 64-bit Windows; the build was verified on Windows 11.
The packaged application does not require a separate Python or FFmpeg installation.

Left-click the artwork to open music. Click elapsed time to show or hide the playlist.
Click total duration to open embedded lyrics; click again to hide the panel.

## Controls

- Round button: left-click to play/pause, right-click to stop.
- Click the waveform to seek. Scroll towards yourself to seek forward, away to seek back.
- Elsewhere in the player, the wheel adjusts volume. Set the seek step using the settings button.
- Create playlist tabs with +, close them with a right-click, and search by track title. Tracks remain only for the current session; tab names are saved.
- Select tracks in Explorer and choose Play: the entire selection opens in one player, with no artificial file-count limit.
- Click the number, title, format or time header to sort the playlist; click again to reverse the order. Column widths adjust automatically.
- Red time to the right of the waveform shows time remaining. Right-click it to display total duration. Each new track starts in remaining-time mode.
- Open and Add music dialogs remember the last selected folder between sessions.
- Embedded lyrics have adjustable text size; their button appears when lyrics are present.
- When embedded artwork is absent, the player uses an image from the track folder: cover, folder, front, or the first suitable filename.
- Repeat modes: stop after track → repeat track → playlist once → loop playlist. A–B and shuffle are available.
- Arrow keys seek ±5 seconds; Home/End change tracks; Space toggles pause.
- Click the logo to toggle always-on-top. Window size and position are saved.
- Click the tray icon to restore the window; its menu offers playback and exit commands.
- Remove and Clear all only remove queue entries; audio files remain on disk.

## Formats

MP3, FLAC, WAV, OGG/OGA, Opus, M4A (AAC and ALAC), AAC, WMA, AIFF/AIF,
APE and WavPack (WV). Corrupt and DRM-protected files are unsupported.
The waveform is analyzed in the background and cached; the first analysis depends on track length.

## Run from source

Install Python 3.12 x64, then run PowerShell in the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\AudioPlayer-run.cmd
```

See [BUILD.md](BUILD.md) for packaging. Application code is licensed under [MIT](LICENSE).
Dependencies retain [their own licenses](THIRD_PARTY_NOTICES.md).
