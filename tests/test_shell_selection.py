"""Реальный COM обработчик: выделение >100 и >32767 символов одним запросом."""
import ctypes
import json
import os
import sys
import uuid
import wave
from pathlib import Path

import pytest

from tests.test_runtime import wait_until

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Shell COM")


def test_com_selection_reaches_player_without_count_or_command_line_limit(qt_app, tmp_path):
    import winreg
    from ctypes import wintypes

    project = Path(__file__).resolve().parents[1]
    version = (project / "VERSION").read_text().strip()
    default_helper = project / "AudioPlayer" / f"AudioPlayerShell-{version}.dll"
    helper = Path(os.environ.get("AUDIOPLAYER_SHELL_HELPER", default_helper))
    if not helper.is_file():
        pytest.skip("Соберите AudioPlayerShell или задайте AUDIOPLAYER_SHELL_HELPER")
    script = tmp_path / "selection_probe.py"
    script.write_text(f'''
import json,sys,traceback,os
from pathlib import Path
sys.path.insert(0,{str(Path(__file__).resolve().parents[1])!r})
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from app.services.open_requests import read_request
from app.services.single_instance import SingleInstance
app=QApplication([])
root=Path(sys.argv[1])
ipc=SingleInstance(root/'ipc')
try:
    paths=read_request(sys.argv[3],directory=root/'requests')
    if ipc.start_or_forward(paths):
        from app.core.settings import SettingsStore
        from app.ui.main_window import PlayerWindow
        from app.ui.theme import apply_theme
        apply_theme(app)
        window=PlayerWindow(SettingsStore(root/'settings.json'))
        window.tray.hide()
        window.volume.setValue(0)
        def receive(paths):
            window.open_paths(paths)
            report={{'queued':[str(p) for p in window.playlist.paths],
                    'source':window.player.media.source().toLocalFile()}}
            temporary=root/'result.tmp'
            temporary.write_text(json.dumps(report),encoding='utf-8')
            temporary.replace(root/'result.json')
        ipc.set_handler(receive)
        timer=QTimer()
        def stop():
            if (root/'stop').exists(): window.close();app.quit()
        timer.timeout.connect(stop)
        timer.start(100)
        QTimer.singleShot(60000,app.quit)
        app.exec()
except BaseException:
    (root/f'error-{{os.getpid()}}.txt').write_text(traceback.format_exc(),encoding='utf-8')
    sys.exit(1)
finally:
    ipc.close()
''', encoding="utf-8")

    class Guid(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

        @classmethod
        def parse(cls, value):
            return cls.from_buffer_copy(uuid.UUID(value.strip("{}")).bytes_le)

    def method(pointer, index, result, *arguments):
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(vtable[index])

    ole = ctypes.OleDLL("ole32")
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(Guid), ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    shell = ctypes.OleDLL("shell32")
    shell.SHParseDisplayName.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD, ctypes.c_void_p]
    shell.SHCreateShellItemArrayFromIDLists.argtypes = [wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                                      ctypes.POINTER(ctypes.c_void_p)]
    clsid_text = "{" + str(uuid.uuid4()) + "}"
    class_path = rf"Software\Classes\CLSID\{clsid_text}"
    key_path = class_path + r"\InProcServer32"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, class_path) as key:
        winreg.SetValueEx(key, "PlayerExecutable", 0, winreg.REG_SZ,
                          str(Path(sys.executable).with_name("pythonw.exe")))
        winreg.SetValueEx(key, "PrefixArguments", 0, winreg.REG_MULTI_SZ, [str(script), str(tmp_path)])
        winreg.SetValueEx(key, "RequestDirectory", 0, winreg.REG_SZ, str(tmp_path / "requests"))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(helper))
        winreg.SetValueEx(key, "ThreadingModel", 0, winreg.REG_SZ, "Apartment")
        winreg.FlushKey(key)
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    executor, selection = ctypes.c_void_p(), ctypes.c_void_p()
    initialized = ctypes.windll.ole32.CoInitialize(None) in (0, 1)
    expected = []
    try:
        clsid = Guid.parse(clsid_text)
        text = ctypes.create_unicode_buffer(40)
        ctypes.windll.ole32.StringFromGUID2(ctypes.byref(clsid), text, 40)
        assert text.value.lower() == clsid_text.lower()
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid_text}\InProcServer32") as key:
            assert winreg.QueryValueEx(key, "")[0] == str(helper)
        execute_iid = Guid.parse("7f9185b0-cb92-43c5-80a9-92277a4f7b54")
        selection_iid = Guid.parse("1c9cd5bb-98e9-4491-a60f-31aacc72b83c")
        ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(execute_iid), ctypes.byref(executor))
        method(executor, 0, ctypes.c_long, ctypes.POINTER(Guid), ctypes.POINTER(ctypes.c_void_p))(
            executor, ctypes.byref(selection_iid), ctypes.byref(selection))
        for stage, count in (("cold", 256), ("warm", 301)):
            paths = []
            for index in range(count):
                name = f"{stage} Трек с пробелами и длинным названием для проверки {index + 1:05}.wav"
                path = tmp_path / name
                with wave.open(str(path), "wb") as audio:
                    audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                    audio.writeframes(b"\x00\x10" * 16000)
                paths.append(path)
            assert sum(len(str(path)) + 3 for path in paths) > 32767
            pidls = (ctypes.c_void_p * len(paths))()
            array = ctypes.c_void_p()
            try:
                for index, path in enumerate(paths[::-1]):
                    pidl = ctypes.c_void_p()
                    shell.SHParseDisplayName(str(path), None, ctypes.byref(pidl), 0, None)
                    pidls[index] = pidl
                shell.SHCreateShellItemArrayFromIDLists(len(paths), pidls, ctypes.byref(array))
                hr = method(selection, 3, ctypes.c_long, ctypes.c_void_p)(selection, array)
                assert hr >= 0, hex(hr & 0xffffffff)
                hr = method(executor, 9, ctypes.c_long)(executor)
                assert hr >= 0, hex(hr & 0xffffffff)
            finally:
                if array:
                    method(array, 2, wintypes.ULONG)(array)
                for pidl in pidls:
                    if pidl:
                        ole.CoTaskMemFree(pidl)
            expected.extend(paths)

            def complete():
                report = tmp_path / "result.json"
                return report.exists() and len(json.loads(report.read_text())["queued"]) == len(expected)

            wait_until(complete, timeout=30000)
            report = json.loads((tmp_path / "result.json").read_text())
            assert set(map(Path, report["queued"])) == set(expected)
            assert Path(report["source"]) == paths[0]
            assert not list((tmp_path / "requests").glob("*.json"))
            assert not list(tmp_path.glob("error-*.txt"))
    finally:
        (tmp_path / "stop").touch()
        if selection:
            method(selection, 2, wintypes.ULONG)(selection)
        if executor:
            method(executor, 2, wintypes.ULONG)(executor)
        if initialized:
            ctypes.windll.ole32.CoUninitialize()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\CLSID\{clsid_text}")
