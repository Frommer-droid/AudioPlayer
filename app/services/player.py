"""Адаптер штатного аудиодвижка Qt."""
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class PlayerService(QObject):
    ended = Signal()
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio = QAudioOutput(self)
        self.media = QMediaPlayer(self)
        self.media.setAudioOutput(self.audio)
        self.audio.setVolume(0.65)
        self.media.mediaStatusChanged.connect(self._status)
        self.media.errorOccurred.connect(lambda _error, message: self.failed.emit(message))

    def open(self, path: Path):
        self.media.setSource(QUrl.fromLocalFile(str(path)))
        self.media.play()

    def toggle(self):
        if self.media.source().isEmpty():
            return
        if self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media.pause()
        else:
            self.media.play()

    def stop(self, reload=True):
        """Освободить renderer; сохранить выбранный трек в остановленном состоянии.

        В Qt 6.12 обычный stop после pause/resume может блокировать следующий
        проход event loop. Сброс source и повторная загрузка проверены отдельно.
        """
        source = self.media.source()
        self.media.setSource(QUrl())
        if reload and not source.isEmpty():
            self.media.setSource(source)

    def _status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.ended.emit()
