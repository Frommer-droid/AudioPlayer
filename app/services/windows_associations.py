"""Исправление собственных Explorer verbs без смены приложений по умолчанию."""
import ctypes
import logging
import sys
from pathlib import Path

APPLICATION_KEY = r"Software\Classes\Applications\AudioPlayer.exe"
SHELL_CLSID = "{45DDC492-B10B-4868-B1F1-F315E79543E8}"


def command_executable(command):
    from ctypes import wintypes

    shell = ctypes.windll.shell32
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    count = ctypes.c_int()
    arguments = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not arguments:
        raise OSError("Некорректная команда AudioPlayer")
    try:
        return Path(arguments[0])
    finally:
        ctypes.windll.kernel32.LocalFree(arguments)


def repair_registered_verbs(application_key=APPLICATION_KEY, helper_path=None, clsid=SHELL_CLSID):
    """Дополняет существующую регистрацию: open/play поддерживают общий плейлист.

    Использует уже выбранную пользователем команду открытия, сохраняя путь к
    portable-копии. Не создаёт ассоциаций расширений и не меняет UserChoice.
    """
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, application_key + r"\shell\open\command") as key:
            command, kind = winreg.QueryValueEx(key, "")
        if kind != winreg.REG_SZ or not isinstance(command, str) or not command.strip():
            return False
        executable = command_executable(command)
        if helper_path is not None:
            helper = Path(helper_path)
        else:
            try:
                version = (executable.parent / "VERSION").read_text(encoding="utf-8-sig").strip()
            except OSError:
                version = ""
            helper = executable.with_name(f"AudioPlayerShell-{version}.dll")
        delegate = helper.is_file()
        changed = False
        values = []
        if delegate:
            class_key = rf"Software\Classes\CLSID\{clsid}"
            values.extend([(class_key, "PlayerExecutable", str(executable)),
                           (class_key + r"\InProcServer32", "", str(helper)),
                           (class_key + r"\InProcServer32", "ThreadingModel", "Apartment")])
        for verb in ("open", "play"):
            values.append((application_key + rf"\shell\{verb}", "MultiSelectModel", "Player"))
            if delegate:
                values.append((application_key + rf"\shell\{verb}\command", "DelegateExecute", clsid))
            if verb == "play":
                values.append((application_key + r"\shell\play\command", "", command))
        for path, name, value in values:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path,
                                    access=winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    current, current_kind = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    current, current_kind = None, None
                if current != value or current_kind != winreg.REG_SZ:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                    changed = True
        if changed:
            # SHCNE_ASSOCCHANGED / SHCNF_IDLIST: invalidate Explorer's association cache.
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        return changed
    except FileNotFoundError:
        return False
    except OSError:
        logging.getLogger(__name__).exception("Не удалось обновить команды AudioPlayer в Проводнике")
        return False
