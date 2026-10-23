"""Добавить версию, справку и legal bundle, не запуская программу."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / "AudioPlayer"
    if not (target / "AudioPlayer.exe").is_file():
        raise RuntimeError("No executable")
    for name in ("VERSION", "LICENSE", "THIRD_PARTY_NOTICES.md", "README.md", "README.en.md"):
        shutil.copy2(ROOT / name, target / name)
    shutil.copytree(ROOT / "legal", target / "legal", dirs_exist_ok=True)
    (target / "docs").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "docs/release-player.png", target / "docs/release-player.png")
    (target / "app/ui/assets").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "app/ui/assets/audioplayer.png", target / "app/ui/assets/audioplayer.png")
    assert not (target / "settings.json").exists(), "Public payload must start with clean settings"


if __name__ == "__main__":
    main()
