"""Explicit public source export; keeps local docs/data in the working project."""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    args.target.mkdir(parents=True, exist_ok=False)
    for directory in ("app", "tests", "tools", "Build_Tools", "legal"):
        shutil.copytree(ROOT / directory, args.target / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in (".gitignore", ".gitattributes", "AudioPlayer.py", "AudioPlayer-run.cmd",
                 "README.md", "README.en.md",
                 "BUILD.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "RELEASE_NOTES.md", "VERSION",
                 "requirements.txt", "requirements-build.txt", "pyproject.toml"):
        shutil.copy2(ROOT / name, args.target / name)
    (args.target / "docs").mkdir()
    for name in ("release-player.png", "settings-preview.png"):
        shutil.copy2(ROOT / "docs" / name, args.target / "docs" / name)
    (args.target / "USAGE.md").write_text(
        "# AudioPlayer\n\nУстановка и управление: [README.md](README.md).\n"
        "Сборка: [BUILD.md](BUILD.md).\n"
        "Настройки и кеш сохраняются рядом с EXE, если папка доступна для записи;\n"
        "иначе — в %LOCALAPPDATA%/AudioPlayer.\n", encoding="utf-8")
    (args.target / "handoff.md").write_text(
        f"# Development handoff\n\nAudioPlayer {(ROOT / 'VERSION').read_text().strip()}, "
        "Windows x64, Python 3.12.\n"
        "Build and verification: BUILD.md. Dependencies: requirements*.txt.\n"
        "Known scope: local audio only; no DRM. No credentials required.\n",
        encoding="utf-8")


if __name__ == "__main__":
    main()
