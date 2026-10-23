"""Атомарное сохранение настроек рядом с программой."""
import json
import os
import sys
import tempfile
from pathlib import Path


def data_root():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[2]
    portable = Path(sys.executable).resolve().parent
    try:
        with tempfile.TemporaryFile(dir=portable):
            pass
        return portable
    except OSError:
        directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AudioPlayer"
        directory.mkdir(parents=True, exist_ok=True)
        return directory


ROOT = data_root()


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or ROOT / "settings.json"

    def load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, data: dict):
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
