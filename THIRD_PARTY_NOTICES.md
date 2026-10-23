# Third-party components

The MIT license in LICENSE applies to the original AudioPlayer code only.
Bundled components retain their copyright notices and licenses in `legal/`.

| Component | Version | License / source |
| --- | --- | --- |
| Python | 3.12 | PSF, https://www.python.org/downloads/source/ |
| PySide6 / Shiboken6 / Qt | 6.12.0 | LGPL/GPL alternatives; https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0 and https://code.qt.io/cgit/qt/qt5.git/tag/?h=v6.12.0 |
| Mutagen | 1.48.1 | GPL-2.0-or-later; https://github.com/quodlibet/mutagen/tree/release-1.48.1 |
| NumPy | 2.5.4 | BSD and bundled component notices; https://github.com/numpy/numpy/tree/v2.5.4 |
| PyAV | 19.0.1 | BSD-3-Clause; https://github.com/PyAV-Org/PyAV/tree/v19.0.1 |
| FFmpeg shared libraries | wheel-specific | LGPL-3.0-or-later as reported by the bundled libraries; https://github.com/PyAV-Org/PyAV (wheel build recipe) and https://ffmpeg.org/download.html |
| Tabler Icons | 3.49.0 | MIT; app/ui/icons/LICENSE.txt and SOURCE.md |

Mutagen is GPL licensed; redistribution of a combined program must respect the
GPL conditions as well as the licenses of its other components. The original
application source remains available under MIT. Third-party source and build
recipes are identified above; dependency versions are pinned in requirements.txt.
Qt and FFmpeg are distributed as separate shared libraries in the onedir bundle.
Users may replace these libraries with compatible modified versions; reverse
engineering for debugging such modifications is not prohibited by AudioPlayer.
No warranty is provided. Audio files and artwork are supplied by the user.
