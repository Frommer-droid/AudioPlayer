"""Файловые запросы для выделений, не помещающихся в командную строку/IPC frame."""
import json
import os
import uuid
from pathlib import Path


def request_directory():
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local / "AudioPlayer" / "shell-requests"


def write_request(paths, directory=None):
    root = Path(directory) if directory is not None else request_directory()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4()}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(list(map(str, paths)), stream, ensure_ascii=False)
    return path


def read_request(path, directory=None):
    root = Path(directory) if directory is not None else request_directory()
    path = Path(path).resolve()
    if path.parent != root.resolve() or path.suffix.lower() != ".json":
        raise ValueError("Файл запроса находится вне каталога AudioPlayer")
    uuid.UUID(path.stem.strip("{}"))
    with path.open(encoding="utf-8-sig") as stream:
        paths = json.load(stream)
    if not isinstance(paths, list) or not all(isinstance(value, str) for value in paths):
        raise ValueError("Некорректный список файлов AudioPlayer")
    # Consuming a request is part of delivery, not cache/build cleanup.
    path.unlink()
    return paths


def launch_paths(arguments):
    if arguments[:1] == ["--open-list"]:
        if len(arguments) != 2:
            raise ValueError("Не указан файл запроса AudioPlayer")
        return read_request(arguments[1])
    return arguments
