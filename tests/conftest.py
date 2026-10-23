"""Общее Qt-приложение для проверок интерфейса."""
import pytest
from PySide6.QtWidgets import QApplication

from app.ui.theme import apply_theme


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    yield app
