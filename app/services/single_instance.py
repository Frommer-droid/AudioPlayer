"""One user-owned player; collect Explorer's per-file launches into one batch."""
import hashlib
import json
import re
import time
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, QThread, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from app.services.open_requests import read_request, write_request

MAX_MESSAGE = 4 * 1024 * 1024


def filename_key(path):
    parts = tuple(int(part) if part.isdigit() else part.casefold()
                  for part in re.split(r"(\d+)", Path(path).name))
    return parts, path.casefold()


class SingleInstance(QObject):
    def __init__(self, directory=None, batch_delay=800):
        super().__init__()
        directory = Path(directory) if directory else Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation))
        directory.mkdir(parents=True, exist_ok=True)
        lock_path = directory / "player-instance.lock"
        digest = hashlib.sha256(str(lock_path.resolve()).casefold().encode("utf-8")).hexdigest()[:24]
        self.name = f"AudioPlayer-{digest}"
        self.lock = QLockFile(str(lock_path))
        self.lock.setStaleLockTime(0)
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.setMaxPendingConnections(128)
        self.server.newConnection.connect(self._accept)
        self._buffers = {}
        self._pending = {}
        self._requested = False
        self._handler = None
        self._delay = batch_delay
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dispatch)

    def start_or_forward(self, paths):
        normalized = [str(Path(path).resolve()) for path in paths]
        payload = json.dumps({"paths": normalized}, ensure_ascii=False).encode("utf-8") + b"\n"
        if len(payload) > MAX_MESSAGE:
            request = write_request(normalized)
            payload = json.dumps({"request_file": str(request)}).encode("utf-8") + b"\n"
        else:
            request = None
        # A lock is necessary on Windows: named pipes allow multiple listeners.
        for _ in range(40):
            if self.lock.tryLock(0):
                QLocalServer.removeServer(self.name)
                if not self.server.listen(self.name):
                    self.lock.unlock()
                    raise RuntimeError(self.server.errorString())
                self._queue(normalized)
                if request is not None:
                    request.unlink(missing_ok=True)
                return True
            if self.lock.error() != QLockFile.LockError.LockFailedError:
                raise RuntimeError("Не удалось заблокировать запуск второго экземпляра")
            if self._forward(payload):
                return False
            QThread.msleep(100)
        raise RuntimeError("Открытый плеер не отвечает. Повторите открытие файлов")

    def _forward(self, payload):
        socket = QLocalSocket()
        try:
            socket.connectToServer(self.name)
            if not socket.waitForConnected(150):
                return False
            socket.write(payload)
            deadline = time.monotonic() + 5
            while socket.bytesToWrite():
                socket.waitForBytesWritten(1000)
                disconnected = socket.state() == QLocalSocket.LocalSocketState.UnconnectedState
                if socket.bytesToWrite() and (time.monotonic() > deadline or disconnected):
                    raise RuntimeError("Не удалось передать файлы открытому плееру")
            response = bytearray()
            while b"\n" not in response:
                if not socket.bytesAvailable() and not socket.waitForReadyRead(5000):
                    raise RuntimeError("Плеер не подтвердил получение файлов")
                response.extend(bytes(socket.readAll()))
                if len(response) > 64 or time.monotonic() > deadline:
                    raise RuntimeError("Некорректный ответ открытого плеера")
            if response != b"OK\n":
                raise RuntimeError("Плеер отклонил список файлов")
            return True
        finally:
            socket.abort()

    def set_handler(self, handler):
        self._handler = handler
        if self._requested:
            self._timer.start(self._delay if self._pending else 0)

    def _queue(self, paths):
        self._requested = True
        for path in paths:
            self._pending[path.casefold()] = path
        if self._handler is not None:
            self._timer.start(self._delay if self._pending else 0)

    def _dispatch(self):
        if self._handler is None or not self._requested:
            return
        paths = sorted(self._pending.values(), key=filename_key)
        self._pending.clear()
        self._requested = False
        self._handler(paths)

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._drop(s))
            self._read(socket)

    def _read(self, socket):
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > MAX_MESSAGE:
            socket.abort()
            return
        if b"\n" not in buffer:
            return
        try:
            message = json.loads(buffer[:buffer.index(b"\n")])
            paths = read_request(message["request_file"]) if "request_file" in message else message["paths"]
            if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
                raise ValueError("Invalid paths")
        except (OSError, ValueError, TypeError, KeyError):
            socket.write(b"ERROR\n")
        else:
            self._queue(paths)
            socket.write(b"OK\n")
        socket.disconnectFromServer()

    def _drop(self, socket):
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def close(self):
        self._timer.stop()
        for socket in list(self._buffers):
            socket.abort()
        self.server.close()
        if self.lock.isLocked():
            self.lock.unlock()
