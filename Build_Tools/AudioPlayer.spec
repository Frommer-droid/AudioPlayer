# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path
import PySide6

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / 'Build_Tools'))
from native_policy import validate_binaries

a = Analysis([str(ROOT / 'AudioPlayer.py')], pathex=[str(ROOT)],
    datas=[(str(ROOT / 'app/ui/icons'), 'app/ui/icons'),
           (str(ROOT / 'app/ui/assets'), 'app/ui/assets')],
    hiddenimports=['mutagen.mp3', 'mutagen.wave', 'mutagen.flac', 'mutagen.oggvorbis',
        'mutagen.oggopus', 'mutagen.oggflac', 'mutagen.mp4', 'mutagen.aac', 'mutagen.asf',
        'mutagen.aiff', 'mutagen.monkeysaudio', 'mutagen.wavpack'],
    excludes=['tkinter', 'pytest', 'ruff', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets'])
a.binaries = validate_binaries(a.binaries, ROOT, Path(PySide6.__file__).parent)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='AudioPlayer',
    debug=False, strip=False, upx=False, console=False,
    icon=str(ROOT / 'app/ui/assets/audioplayer.ico'), version=str(ROOT / 'Build_Tools/version_info.txt'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='AudioPlayer')
