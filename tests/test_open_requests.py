"""Выделение больше IPC frame передаётся целиком через одноразовый JSON запрос."""
import json

import pytest

from app.services.open_requests import launch_paths, read_request, request_directory, write_request
from app.services.single_instance import MAX_MESSAGE, SingleInstance
from tests.test_runtime import wait_until
from tests.test_single_instance import launch_client


def test_large_selection_is_not_limited_by_ipc_frame(qt_app, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    paths = [str(tmp_path / ("x" * 150) / ("y" * 150) / f"{i:05}.wav") for i in range(16000)]
    assert len(json.dumps({"paths": paths}).encode()) > MAX_MESSAGE
    ipc = SingleInstance(tmp_path / "ipc", batch_delay=20)
    assert ipc.start_or_forward([])
    batches = []
    ipc.set_handler(batches.append)
    request = write_request(paths)
    client = launch_client(tmp_path / "ipc", ["--open-list", request])
    try:
        wait_until(lambda: client.poll() is not None and any(len(batch) == len(paths) for batch in batches),
                   timeout=20000)
        assert client.returncode == 0, client.communicate()[1].decode(errors="replace")
        assert next(batch for batch in batches if batch) == paths
        assert not list(request_directory().glob("*.json"))
    finally:
        ipc.close()
        if client.poll() is None:
            client.kill()
        client.communicate()


def test_request_is_consumed_and_foreign_files_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    values = ["D:/Музыка/Трек с пробелами.mp3", "D:/Music/another.wav"]
    request = write_request(values)
    assert launch_paths(["--open-list", str(request)]) == values
    assert not request.exists()
    foreign = tmp_path / "user.json"
    foreign.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError):
        read_request(foreign)
    assert foreign.exists()
    assert launch_paths(values) == values
    with pytest.raises(ValueError):
        launch_paths(["--open-list"])
