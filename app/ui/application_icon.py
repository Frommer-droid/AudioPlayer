"""Единый знак приложения для заголовка, Windows и системного лотка."""
from pathlib import Path

from PySide6.QtGui import QIcon

ICON_PATH = Path(__file__).with_name("assets") / "audioplayer.ico"


def application_icon():
    return QIcon(str(ICON_PATH))
