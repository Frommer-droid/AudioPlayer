"""Реальные Windows play verbs и передача двадцати файлов без чужих ассоциаций."""
import ctypes
import json
import subprocess
import sys
import uuid
import wave
from pathlib import Path

import pytest

from app.services.windows_associations import repair_registered_verbs
from tests.test_runtime import wait_until

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Shell")


@pytest.fixture
def association_key():
    import winreg

    key = "Software\\Classes\\Applications\\AudioPlayer-test-" + uuid.uuid4().hex + ".exe"
    yield key

    def remove(path):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as handle:
                children = [winreg.EnumKey(handle, i) for i in range(winreg.QueryInfoKey(handle)[0])]
            for child in children:
                remove(path + "\\" + child)
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass

    assert key.startswith("Software\\Classes\\Applications\\AudioPlayer-test-")
    remove(key)


def set_open_command(key, command, kind=None):
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key + r"\shell\open\command") as handle:
        winreg.SetValueEx(handle, "", 0, kind or winreg.REG_SZ, command)


def test_repair_keeps_open_command_and_is_idempotent(association_key):
    import winreg

    command = r'"D:\Музыка и программы\AudioPlayer.exe" "%1"'
    set_open_command(association_key, command)
    assert repair_registered_verbs(association_key)
    assert not repair_registered_verbs(association_key)
    for verb in ("open", "play"):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key + rf"\shell\{verb}") as handle:
            assert winreg.QueryValueEx(handle, "MultiSelectModel")[0] == "Player"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key + rf"\shell\{verb}\command") as handle:
            assert winreg.QueryValueEx(handle, "")[0] == command


def test_missing_registration_and_invalid_command_are_not_created(association_key):
    import winreg

    assert not repair_registered_verbs(association_key)
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key)
    set_open_command(association_key, 42, winreg.REG_DWORD)
    assert not repair_registered_verbs(association_key)
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key + r"\shell\play")


def test_read_only_registration_does_not_abort_startup(association_key, monkeypatch):
    import winreg

    set_open_command(association_key, '"AudioPlayer.exe" "%1"')

    def denied(*args):
        raise PermissionError("Test registry access denied")

    monkeypatch.setattr(winreg, "SetValueEx", denied)
    assert not repair_registered_verbs(association_key)


def test_delegate_preserves_executable_and_uses_versioned_dll(association_key, tmp_path):
    import winreg

    executable = tmp_path / "AudioPlayer.exe"
    executable.touch()
    (tmp_path / "VERSION").write_text("0.2.6", encoding="utf-8")
    helper = tmp_path / "AudioPlayerShell-0.2.6.dll"
    helper.touch()
    clsid = "{" + str(uuid.uuid4()) + "}"
    class_key = rf"Software\Classes\CLSID\{clsid}"
    command = f'"{executable}" "%1"'
    set_open_command(association_key, command)
    try:
        assert repair_registered_verbs(association_key, clsid=clsid)
        assert not repair_registered_verbs(association_key, clsid=clsid)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, class_key + r"\InProcServer32") as key:
            assert winreg.QueryValueEx(key, "")[0] == str(helper)
            assert winreg.QueryValueEx(key, "ThreadingModel")[0] == "Apartment"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, class_key) as key:
            assert winreg.QueryValueEx(key, "PlayerExecutable")[0] == str(executable)
        for verb in ("open", "play"):
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key + rf"\shell\{verb}\command") as key:
                assert winreg.QueryValueEx(key, "DelegateExecute")[0] == clsid
                assert winreg.QueryValueEx(key, "")[0] == command
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, class_key + r"\InProcServer32")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, class_key)


def test_native_play_verb_delivers_twenty_cold_and_twenty_warm(qt_app, tmp_path, association_key):
    import winreg
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR),
                    ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                    ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    script = tmp_path / "native_play_probe.py"
    script.write_text(f'''
import json, os, sys, traceback
from pathlib import Path
sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r})
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.services.single_instance import SingleInstance
app=QApplication([])
root=Path(sys.argv[1])
ipc=SingleInstance(root/'ipc')
try:
    primary=ipc.start_or_forward(sys.argv[2:])
    if primary:
        from app.core.settings import SettingsStore
        from app.ui.main_window import PlayerWindow
        from app.ui.theme import apply_theme
        apply_theme(app)
        window=PlayerWindow(SettingsStore(root/'settings.json'))
        window.tray.hide()
        window.volume.setValue(0)
        seen={{}}
        def receive(paths):
            window.open_paths(paths)
            for path in paths: seen[path.casefold()]=path
            temporary=root/'result.tmp'
            report={{'received':list(seen.values()),'queued':[str(p) for p in window.playlist.paths],
                    'source':window.player.media.source().toLocalFile()}}
            temporary.write_text(json.dumps(report),encoding='utf-8')
            temporary.replace(root/'result.json')
        ipc.set_handler(receive)
        QTimer.singleShot(45000,app.quit)
        app.exec()
except BaseException:
    (root/f'error-{{os.getpid()}}.txt').write_text(traceback.format_exc(),encoding='utf-8')
    sys.exit(1)
finally:
    ipc.close()
''', encoding="utf-8")
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    command = subprocess.list2cmdline([str(pythonw), str(script), str(tmp_path)]) + ' "%1"'
    set_open_command(association_key, command)
    assert repair_registered_verbs(association_key)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    initialized = ctypes.windll.ole32.CoInitialize(None) in (0, 1)
    handles = []
    expected = []

    def received():
        report = tmp_path / "result.json"
        return json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}

    try:
        for stage in ("cold", "warm"):
            for index in range(20):
                path = tmp_path / f"{stage} Трек с пробелами {index + 1:02}.wav"
                with wave.open(str(path), "wb") as audio:
                    audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\x00\x10" * 16000)
                expected.append(str(path.resolve()))
                info = ShellExecuteInfo()
                info.cbSize = ctypes.sizeof(info)
                info.fMask = 0x3 | 0x40 | 0x400  # CLASSKEY | NOCLOSEPROCESS | FLAG_NO_UI
                info.lpVerb, info.lpFile = "play", str(path)
                info.lpClass = association_key.removeprefix("Software\\Classes\\")
                info.lpDirectory = str(tmp_path)
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, association_key) as key:
                    info.hkeyClass = int(key)
                    assert shell.ShellExecuteExW(ctypes.byref(info)), ctypes.get_last_error()
                assert info.hProcess
                handles.append(info.hProcess)
            wait_until(lambda: set(received().get("received", [])) == set(expected), timeout=25000)
            report = received()
            assert set(report["queued"]) == set(expected)
            assert Path(report["source"]) == tmp_path / f"{stage} Трек с пробелами 01.wav"
            assert not list(tmp_path.glob("error-*.txt"))
    finally:
        for handle in handles:
            if kernel.WaitForSingleObject(handle, 0) == 258:
                kernel.TerminateProcess(handle, 0)
            kernel.CloseHandle(handle)
        if initialized:
            ctypes.windll.ole32.CoUninitialize()
