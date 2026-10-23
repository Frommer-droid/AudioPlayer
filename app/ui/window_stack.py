"""Изменение z-order Windows без пересоздания, перемещения или показа окон."""
import ctypes
import sys
from ctypes import wintypes
from functools import lru_cache

from PySide6.QtCore import Qt


@lru_cache(maxsize=1)
def _user32():
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
    api.SetWindowPos.restype = wintypes.BOOL
    get_style = api.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else api.GetWindowLongW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    return api.SetWindowPos, get_style


def set_topmost(window, enabled):
    if sys.platform != "win32":
        visible = window.isVisible()
        window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if visible:
            window.show()
        return
    # Do not create native handles for hidden, never-shown panels.
    # Their Show event applies the current preference when they are created.
    if window.windowHandle() is None:
        return
    handle = int(window.winId())
    set_position, get_style = _user32()
    if bool(get_style(handle, -20) & 0x00000008) == enabled:  # GWL_EXSTYLE / WS_EX_TOPMOST
        return
    insert_after = -1 if enabled else -2  # HWND_TOPMOST / HWND_NOTOPMOST
    flags = 0x0001 | 0x0002 | 0x0010 | 0x0200  # NOSIZE | NOMOVE | NOACTIVATE | NOOWNERZORDER
    if not set_position(handle, insert_after, 0, 0, 0, 0, flags):
        raise ctypes.WinError(ctypes.get_last_error())
