"""Real Windows IPC: race-free election, Explorer batching and warm delivery."""
import json
import shutil
import subprocess
import sys

from PySide6.QtMultimedia import QMediaPlayer

from app.core.settings import SettingsStore
from app.services.single_instance import SingleInstance
from app.ui.main_window import PlayerWindow
from tests.test_open_files import make_tracks
from tests.test_runtime import wait_until

CLIENT = """
import sys
from PySide6.QtCore import QCoreApplication
from app.services.single_instance import SingleInstance
from app.services.open_requests import launch_paths
app=QCoreApplication([])
ipc=SingleInstance(sys.argv[1])
try:
    assert not ipc.start_or_forward(launch_paths(sys.argv[2:])), 'Secondary became primary'
finally:
    ipc.close()
"""


def launch_client(directory, paths):
    return subprocess.Popen([sys.executable, "-c", CLIENT, str(directory), *map(str, paths)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_forwarded_files_form_one_sorted_batch_and_start_first(qt_app, tmp_path):
    names = ["10 Трек.wav", "2 Трек.wav", "Я Трек.wav"]
    paths = []
    for old, name in zip(make_tracks(tmp_path), names):
        new = tmp_path / name
        old.rename(new)
        paths.append(new)
    directory = tmp_path / "ipc"
    ipc = SingleInstance(directory, batch_delay=500)
    assert ipc.start_or_forward([paths[0]])
    window = PlayerWindow(SettingsStore(tmp_path / "settings.json"))
    window.volume.setValue(0)
    batches = []

    def receive(values):
        batches.append(values)
        if values:
            window.open_paths(values)

    ipc.set_handler(receive)
    clients = [launch_client(directory, [path]) for path in (paths[2], paths[1], paths[1])]
    try:
        wait_until(lambda: all(client.poll() is not None for client in clients))
        for client in clients:
            assert client.returncode == 0, client.communicate()[1].decode(errors="replace")
        wait_until(lambda: bool(batches))
        expected = [paths[1], paths[0], paths[2]]
        assert batches == [[str(path) for path in expected]]
        assert window.playlist.paths == expected
        assert window.playlist.current == 0
        wait_until(lambda: window.player.media.position() > 0)
        assert window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        new_path = tmp_path / "1 Дополнительный.wav"
        shutil.copyfile(paths[0], new_path)
        warm = launch_client(directory, [new_path])
        clients.append(warm)
        wait_until(lambda: warm.poll() is not None and len(batches) == 2)
        assert warm.returncode == 0
        assert window.playlist.paths[-1] == new_path
        assert window.playlist.paths[window.playlist.current] == new_path
        source = window.player.media.source()
        wake = launch_client(directory, [])
        clients.append(wake)
        wait_until(lambda: wake.poll() is not None and len(batches) == 3)
        assert wake.returncode == 0 and batches[-1] == []
        assert window.player.media.source() == source
    finally:
        ipc.close()
        window.close()
        for client in clients:
            if client.poll() is None:
                client.kill()
            client.communicate()


def test_simultaneous_cold_starts_elect_exactly_one_process(qt_app, tmp_path):
    script = tmp_path / "cold_start.py"
    script.write_text('''
import json,os,sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication,QTimer
from app.services.single_instance import SingleInstance
app=QCoreApplication([])
root=Path(sys.argv[1])
ipc=SingleInstance(root/'ipc')
if not ipc.start_or_forward(sys.argv[2:]):
    sys.exit(0)
with (root/'primary.txt').open('x') as f:
    f.write(str(os.getpid()))
batches=[]
def receive(paths):
    batches.append(paths)
    if len(paths)==4:
        (root/'result.json').write_text(json.dumps({'pid':os.getpid(),'batches':batches}),encoding='utf-8')
        app.quit()
ipc.set_handler(receive)
QTimer.singleShot(12000,app.quit)
app.exec()
ipc.close()
sys.exit(0 if (root/'result.json').exists() else 1)
''', encoding="utf-8")
    import os
    from pathlib import Path
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    paths = [str(tmp_path / name) for name in ("Я.wav", "10.wav", "2.wav", "А.wav")]
    clients = [subprocess.Popen([sys.executable, str(script), str(tmp_path), path],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for path in paths]
    try:
        wait_until(lambda: all(client.poll() is not None for client in clients), timeout=16000)
        for client in clients:
            assert client.returncode == 0, client.communicate()[1].decode(errors="replace")
        result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
        assert str(result["pid"]) == (tmp_path / "primary.txt").read_text()
        assert result["batches"] == [[paths[2], paths[1], paths[3], paths[0]]]
    finally:
        for client in clients:
            if client.poll() is None:
                client.kill()
            client.communicate()


def test_dead_primary_lock_does_not_prevent_restart(qt_app, tmp_path):
    code = """
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from app.services.single_instance import SingleInstance
app=QCoreApplication([])
ipc=SingleInstance(sys.argv[1])
assert ipc.start_or_forward([])
Path(sys.argv[2]).write_text('ready')
app.exec()
"""
    ready = tmp_path / "ready.txt"
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path / "ipc"), str(ready)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_until(ready.exists)
        child.kill()
        child.communicate(timeout=5)
        replacement = SingleInstance(tmp_path / "ipc")
        try:
            assert replacement.start_or_forward([])
        finally:
            replacement.close()
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate()
