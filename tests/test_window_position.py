"""Native restart checks at the work-area edges, including the top taskbar."""
import pytest
from PySide6.QtCore import QPoint

from app.core.settings import SettingsStore
from app.ui.main_window import PlayerWindow


@pytest.mark.parametrize("edge", ["top", "bottom", "left", "right"])
def test_restart_at_work_area_edge(qt_app, tmp_path, edge):
    store = SettingsStore(tmp_path / "settings.json")
    window = PlayerWindow(store)
    window.show()
    qt_app.processEvents()
    area = window.screen().availableGeometry()
    x = area.left() + (area.width() - window.width()) // 2
    y = area.top() + (area.height() - window.height()) // 2
    if edge == "top":
        y = area.top()
    elif edge == "bottom":
        y = area.bottom() - window.height() + 1
    elif edge == "left":
        x = area.left()
    else:
        x = area.right() - window.width() + 1
    expected = QPoint(x, y)
    window.move(expected)
    qt_app.processEvents()
    size = window.size()
    window.close()
    for _ in range(5):
        window = PlayerWindow(store)
        try:
            window.show()
            qt_app.processEvents()
            assert window.pos() == expected
            assert window.size() == size
        finally:
            window.close()


@pytest.mark.parametrize("replacement", [
    {"position": [0]}, {"position": [True, 40]}, {"position": [2**60, 40]},
    {"position": [-100000, -100000]}, {"available_geometry": [0, 0, 1, 1]},
    {"geometry": "invalid", "position": [0, 0]},
])
def test_invalid_or_obsolete_position_keeps_qt_restoration(qt_app, tmp_path, replacement):
    store = SettingsStore(tmp_path / "settings.json")
    original = PlayerWindow(store)
    original.show()
    qt_app.processEvents()
    area = original.screen().availableGeometry()
    original.move(area.left() + 160, area.top() + 160)
    original.close()
    data = store.load()
    data["window"].update(replacement)
    store.save(data)
    baseline = dict(data["window"])
    baseline.pop("position", None)
    data["window"] = baseline
    baseline_store = SettingsStore(tmp_path / "baseline.json")
    baseline_store.save(data)
    expected = PlayerWindow(baseline_store)
    actual = PlayerWindow(store)
    try:
        expected.show()
        actual.show()
        qt_app.processEvents()
        assert actual.pos() == expected.pos()
        assert actual.size() == expected.size()
    finally:
        actual.close()
        expected.close()
