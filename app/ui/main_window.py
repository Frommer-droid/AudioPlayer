"""Главное окно; команды пользователя передаются сервисам и модели."""
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
    QStyleOptionViewItem,
    QSystemTrayIcon,
    QTableWidgetItem,
    QWidget,
)

from app.core.playlist import AUDIO_FILE_FILTER, SUPPORTED, format_time
from app.core.playlist_collection import PlaylistCollection
from app.core.settings import SettingsStore
from app.services.cover_art import folder_cover
from app.services.duration import read_duration_ms
from app.services.metadata import read_metadata
from app.services.player import PlayerService
from app.services.waveform import WaveformService
from app.ui.application_icon import application_icon
from app.ui.controls import SideGrip
from app.ui.player_layout import PLAYER_HEIGHT, build_player
from app.ui.window_stack import set_topmost


def integer(value, default, minimum, maximum):
    try:
        return max(minimum, min(maximum, int(value)))
    except (ValueError, TypeError, OverflowError):
        return default


class PlayerWindow(QMainWindow):
    def __init__(self, store=None):
        super().__init__()
        self.store = store or SettingsStore()
        self.saved = self.store.load()
        self._last_directory = self.saved.get("last_directory", "")
        self.collection = PlaylistCollection(self.saved)
        self.playlist = self.collection.playlists[self.collection.active]
        self._playing_playlist = self.collection.playlists[self.collection.playing]
        self.player = PlayerService(self)
        self.wave_service = WaveformService(self)
        self._technical_info = "Аудиофайл"
        self._bitrate_info = ""
        self._repeat_mode = "off"
        self._always_on_top = False
        self._volume_wheel_delta = 0
        self._ab_start = None
        self._ab_end = None
        self._show_remaining_time = True
        self._display_position = 0
        self._display_duration = 0
        self.setWindowTitle("AudioPlayer")
        self.setWindowIcon(application_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(860, PLAYER_HEIGHT)
        self.setFixedHeight(PLAYER_HEIGHT)
        self.setAcceptDrops(True)
        self._create_ui()
        self.setMinimumWidth(self.centralWidget().minimumSizeHint().width())
        self._left_grip = SideGrip(self, Qt.Edge.LeftEdge)
        self._right_grip = SideGrip(self, Qt.Edge.RightEdge)
        self._update_resize_grips()
        self._connect()
        self._restore()
        self._set_remaining_time(True)
        self._refresh()
        self._shortcuts()
        self._create_tray()
        QApplication.instance().installEventFilter(self)

    def _create_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_menu = QMenu(self)
        self.tray_menu.addAction("Показать плеер", self._restore_from_tray)
        self.tray_menu.addAction("Воспроизведение / пауза", self._toggle)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("Выход", self.close)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _toggle_on_top(self):
        self._set_on_top(self.brand_mark.isChecked())

    def _set_on_top(self, enabled):
        for window in (self, self.library, self.preferences):
            set_topmost(window, enabled)
        self._always_on_top = enabled
        self.brand_mark.setChecked(enabled)
        state = "включено" if enabled else "выключено"
        self.brand_mark.setAccessibleDescription(f"Поверх всех окон: {state}. Нажмите для переключения")

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self._restore_from_tray()

    def _restore_from_tray(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ToolTip:
            return True
        if event.type() == QEvent.Type.Show and watched in (self, self.library, self.preferences):
            set_topmost(watched, self._always_on_top)
        if (event.type() in (QEvent.Type.ShortcutOverride, QEvent.Type.KeyPress)
                and isinstance(watched, QWidget) and watched.window() is self
                and QApplication.activeWindow() is self and not event.modifiers()
                and event.key() in self._playback_keys):
            event.accept()
            if event.type() == QEvent.Type.KeyPress:
                if not event.isAutoRepeat() or event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                    self._playback_keys[event.key()]()
            return True
        if (event.type() == QEvent.Type.Wheel and isinstance(watched, QWidget)
                and watched.window() is self):
            position = self.wave.mapFromGlobal(event.globalPosition().toPoint())
            if self.wave.rect().contains(position):
                self.wave.wheelEvent(event)
            else:
                delta = event.angleDelta().y() or event.pixelDelta().y() * 3
                self._volume_wheel_delta += -delta if event.inverted() else delta
                steps = int(self._volume_wheel_delta / 120)
                self._volume_wheel_delta -= steps * 120
                self.volume.setValue(self.volume.value() - steps * 5)
                event.accept()
            return True
        return super().eventFilter(watched, event)

    def _create_ui(self):
        build_player(self)

    def _connect(self):
        self.wave.seek.connect(self.player.media.setPosition)
        self.player.media.positionChanged.connect(self._position)
        self.player.media.durationChanged.connect(self._duration)
        self.player.media.playbackStateChanged.connect(self._state)
        self.player.ended.connect(self._ended, Qt.ConnectionType.QueuedConnection)
        self.player.failed.connect(
            lambda text: self.statusBar().showMessage(f"Не удалось воспроизвести: {text}"))
        self.wave_service.ready.connect(self.wave.set_peaks)
        self.wave_service.failed.connect(self._wave_failed)
        self.volume.valueChanged.connect(self._volume)
        self.shuffle.toggled.connect(lambda _checked: self._playing_playlist.visited.clear())
        self.wheel_step.valueChanged.connect(lambda value: setattr(self.wave, "step", value * 1000))
        self.statusBar().messageChanged.connect(self._notice_changed)

    def _restore(self):
        self._set_on_top(self.saved.get("always_on_top") is True)
        self.volume.setValue(integer(self.saved.get("volume"), 65, 0, 100))
        self._volume(self.volume.value())
        self.wheel_step.setValue(integer(self.saved.get("wheel_step"), 5, 1, 60))
        self.shuffle.setChecked(self.saved.get("shuffle") is True)
        mode = self.saved.get("repeat_mode")
        if mode not in ("off", "queue", "playlist", "track"):
            mode = "playlist" if self.saved.get("repeat") is True else "off"
        self._set_repeat_mode(mode)
        window = self.saved.get("window", {})
        geometry = window.get("geometry") if isinstance(window, dict) else None
        restored = False
        if isinstance(geometry, str):
            restored = self.restoreGeometry(
                QByteArray.fromBase64(geometry.encode("ascii", errors="ignore")))
        if not isinstance(window, dict) or window.get("layout_version") != 2:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)
            self.resize(860, PLAYER_HEIGHT)
        elif restored:
            self._restore_frameless_position(window)

    def _restore_frameless_position(self, saved):
        # Qt reserves caption space at the top even for this frameless window.
        # Use the exact position only on an unchanged, fully available screen.
        position = saved.get("position")
        area = saved.get("available_geometry")
        if not (isinstance(position, list) and len(position) == 2
                and isinstance(area, list) and len(area) == 4
                and all(type(value) is int and -(2**31) < value < 2**31
                        for value in position + area)):
            return
        point = QPoint(*position)
        bounds = QRect(point, self.size())
        if any(screen.availableGeometry() == QRect(*area)
               and screen.availableGeometry().contains(bounds)
               for screen in QApplication.screens()):
            self.move(point)

    def _show_playlist(self):
        self.library.show_playlist()
        self.library.show_docked()
        self.library.raise_()
        self.library.activateWindow()

    def _toggle_playlist(self):
        if self.library.isVisible():
            self.library.hide_panel()
        else:
            self._show_playlist()

    def _show_lyrics(self):
        if self.library.lyrics_text.toPlainText().strip():
            if not self.library.isVisible():
                self.library.show_docked()
            self.library.show_lyrics()
            self.library.raise_()
            self.library.activateWindow()

    def _toggle_lyrics(self):
        if self.library.isVisible() and self.library.pages.currentIndex() == 1:
            self.library.hide_panel()
        else:
            self._show_lyrics()

    def _add_playlist(self):
        playlist = self.collection.add()
        index = self.library.tabs.addTab(playlist.name)
        self.library.tabs.setCurrentIndex(index)

    def _select_playlist(self, index):
        if not 0 <= index < len(self.collection.playlists):
            return
        self.playlist.search = self.library.search.text()
        self.playlist.selection = max(0, self.table.currentRow())
        self.collection.active = index
        self.playlist = self.collection.playlists[index]
        self.library.search.blockSignals(True)
        self.library.search.setText(self.playlist.search)
        self.library.search.blockSignals(False)
        self.library.show_playlist()
        self._refresh(self.playlist.selection)

    def _close_playlist(self, index):
        playlists = self.collection.playlists
        if not 0 <= index < len(playlists):
            return
        closed = playlists[index]
        playing_closed = closed is self._playing_playlist
        lyrics_visible = self.library.pages.currentIndex() == 1
        if playing_closed:
            self._clear_current_track()
        playlists.pop(index)
        if not playlists:
            self.collection.add("Плейлист")
        active = self.playlist if self.playlist in playlists else playlists[min(index, len(playlists) - 1)]
        if playing_closed:
            self._playing_playlist = active
            active.current = -1
        self.collection.active = playlists.index(active)
        self.collection.playing = playlists.index(self._playing_playlist)
        tabs = self.library.tabs
        tabs.blockSignals(True)
        tabs.removeTab(index)
        if tabs.count() == 0:
            tabs.addTab(active.name)
        tabs.setCurrentIndex(self.collection.active)
        tabs.blockSignals(False)
        self._select_playlist(self.collection.active)
        if lyrics_visible and not playing_closed:
            self.library.show_lyrics()

    def _cycle_repeat(self):
        modes = ("off", "track", "queue", "playlist")
        self._set_repeat_mode(modes[(modes.index(self._repeat_mode) + 1) % len(modes)])

    def _set_repeat_mode(self, mode):
        self._repeat_mode = mode
        self.repeat.setChecked(mode != "off")
        self.repeat.symbol = {"track": "repeat_one", "queue": "playlist_play"}.get(mode, "repeat")
        labels = {"off": "Остановиться после текущего трека", "playlist": "Плейлист по кругу",
                  "track": "Повтор текущего трека", "queue": "Плейлист один раз, затем остановиться"}
        label = labels[mode]
        self.repeat.setText(label)
        self.repeat.setAccessibleName(label)
        self.repeat.setAccessibleDescription(f"{label}. Нажмите для смены режима")
        self.repeat.update()

    def _show_settings(self):
        self.preferences.show()
        self.preferences.raise_()
        self.preferences.activateWindow()

    def _show_menu(self):
        menu = QMenu(self)
        for label, callback in (("Открыть файлы…\tCtrl+O", self._open_files),
                                ("Добавить папку…", self._add_folder),
                                ("Плейлист\tCtrl+L", self._show_playlist),
                                ("Настройки\tCtrl+P", self._show_settings)):
            menu.addAction(label, callback)
        menu.addSeparator()
        menu.addAction("Выход", self.close)
        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def _notice_changed(self, text):
        self.track_info.setText(text or self._bitrate_info)
        self.track_info.setAccessibleDescription(text or self._technical_info)

    def _show_metadata(self, path):
        metadata = read_metadata(path)
        self.track_title.setText(metadata.heading)
        self.file_format.setText(metadata.file_format)
        self.sample_rate.setText(f"{metadata.sample_rate / 1000:g} kHz" if metadata.sample_rate else "")
        self._technical_info = metadata.technical
        self._bitrate_info = f"{round(metadata.bitrate / 1000)} kbps" if metadata.bitrate else ""
        self._notice_changed("")
        self.cover.set_cover(metadata.cover or folder_cover(path))
        self.library.set_lyrics(metadata.lyrics)

    def _mute(self):
        muted = self.mute_button.isChecked()
        self.player.audio.setMuted(muted)
        self.mute_button.setAccessibleDescription("Включить звук" if muted else "Выключить звук")

    def _mark_ab(self):
        position = self.player.media.position()
        if not self.player.media.duration():
            self.ab_button.setChecked(False)
            return
        if self._ab_start is None:
            self._ab_start = position
            self.ab_button.setAccessibleDescription(f"A: {format_time(position)}. Поставить точку B")
            self.ab_button.setChecked(True)
        elif self._ab_end is None:
            if position <= self._ab_start + 100:
                self.statusBar().showMessage("Точка B должна находиться позже A", 3000)
            else:
                self._ab_end = position
                self.ab_button.setAccessibleDescription("A–B: повтор фрагмента. Нажмите, чтобы выключить")
            self.ab_button.setChecked(True)
        else:
            self._clear_ab()

    def _clear_ab(self):
        self._ab_start = self._ab_end = None
        self.ab_button.setChecked(False)
        self.ab_button.setAccessibleDescription("Повтор фрагмента: поставить точку A")

    def _shortcuts(self):
        self._playback_keys = {
            Qt.Key.Key_Right: lambda: self._seek_relative(5000),
            Qt.Key.Key_Left: lambda: self._seek_relative(-5000),
            Qt.Key.Key_Home: lambda: self._advance(-1),
            Qt.Key.Key_End: lambda: self._advance(1),
            Qt.Key.Key_Space: self._toggle,
        }
        self.shortcuts = []
        for key, callback in [("Ctrl+O", self._open_files),
                              ("Ctrl+Right", lambda: self._advance(1)),
                              ("Ctrl+Left", lambda: self._advance(-1)),
                              ("Ctrl+L", self._show_playlist), ("Ctrl+P", self._show_settings),
                              ("Delete", self._remove)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def _seek_relative(self, milliseconds):
        duration = self.player.media.duration()
        if duration > 0:
            self.player.media.setPosition(max(0, min(duration, self.player.media.position() + milliseconds)))

    def add_paths(self, paths):
        count = self.playlist.add(paths)
        self._refresh()
        self.statusBar().showMessage(f"Добавлено файлов: {count}", 5000)

    def _add_files(self):
        self._select_files(play_selected=False)

    def _open_files(self):
        self._select_files(play_selected=True)

    def _select_files(self, *, play_selected):
        title = "Открыть музыку" if play_selected else "Добавить музыку"
        paths, _ = QFileDialog.getOpenFileNames(self, title, self._dialog_directory(), AUDIO_FILE_FILTER)
        if not paths:
            return
        self._remember_directory(Path(paths[0]).parent)
        if play_selected:
            self.open_paths(paths)
        else:
            self.add_paths(paths)

    def open_paths(self, paths):
        paths = list(paths)
        self.add_paths(paths)
        indices = {str(path).casefold(): i for i, path in enumerate(self.playlist.paths)}
        for value in paths:
            try:
                index = indices.get(str(Path(value).resolve()).casefold())
            except (OSError, ValueError, TypeError):
                continue
            if index is not None and self.playlist.paths[index].is_file():
                self._remember_directory(self.playlist.paths[index].parent)
                self.play(index)
                break

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Папка с музыкой", self._dialog_directory())
        if folder:
            try:
                self._remember_directory(folder)
                self.add_paths(sorted(Path(folder).iterdir()))
            except OSError as error:
                self.statusBar().showMessage(f"Не удалось открыть папку: {error}")

    def _dialog_directory(self):
        try:
            if isinstance(self._last_directory, str) and self._last_directory:
                if Path(self._last_directory).is_dir():
                    return self._last_directory
        except (OSError, ValueError):
            pass
        return ""

    def _remember_directory(self, directory):
        try:
            path = Path(directory).resolve()
            if path.is_dir():
                self._last_directory = str(path)
        except (OSError, ValueError):
            pass

    def _sort_playlist(self, column):
        playlist = self.playlist
        selected_paths = {playlist.paths[item.row()] for item in self.table.selectedItems()}
        playlist.sort_descending = column == playlist.sort_column and not playlist.sort_descending
        playlist.sort_column = column
        self._refresh()
        self.table.clearSelection()
        for row, path in enumerate(playlist.paths):
            if path in selected_paths and not self.table.isRowHidden(row):
                for col in range(self.table.columnCount()):
                    self.table.item(row, col).setSelected(True)

    def _refresh(self, selection=None):
        selected = self.table.currentRow() if selection is None else selection
        playlist = self.playlist
        numbers = {path: i + 1 for i, path in enumerate(playlist.original_paths)}
        if playlist.sort_column is not None:
            playlist.selection = selected
            keys = {
                0: lambda path: numbers[path],
                1: lambda path: path.stem.casefold(),
                2: lambda path: path.suffix.casefold(),
                3: lambda path: (read_duration_ms(path) is None, read_duration_ms(path) or 0),
            }
            playlist.sort(keys[playlist.sort_column], playlist.sort_descending)
            selected = playlist.selection
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(playlist.sort_column is not None)
        if playlist.sort_column is not None:
            order = Qt.SortOrder.DescendingOrder if playlist.sort_descending else Qt.SortOrder.AscendingOrder
            header.setSortIndicator(playlist.sort_column, order)
        self.table.setRowCount(len(self.playlist.paths))
        self.table.ensurePolished()
        number_width = 0
        option = QStyleOptionViewItem()
        option.initFrom(self.table)
        option.font = self.table.font()
        option.widget = self.table
        delegate = self.table.itemDelegate()
        for i, path in enumerate(self.playlist.paths):
            playing = self.playlist is self._playing_playlist and i == self.playlist.current
            marker = "▶" if playing else str(numbers[path])
            duration = read_duration_ms(path)
            duration_text = format_time(duration) if duration is not None else "—"
            for column, text in enumerate((marker, path.stem, path.suffix[1:].upper(), duration_text)):
                item = QTableWidgetItem(text)
                alignment = Qt.AlignmentFlag.AlignLeft if column == 1 else Qt.AlignmentFlag.AlignHCenter
                item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, column, item)
                if column == 0:
                    # Let Qt include QSS padding and the delegate's text margins.
                    # Measure the number even when this row shows the play marker.
                    item.setText(str(numbers[path]))
                    index = self.table.model().index(i, column)
                    number_width = max(number_width, delegate.sizeHint(option, index).width())
                    item.setText(marker)
                    number_width = max(number_width, delegate.sizeHint(option, index).width())
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setSizeHint(QSize(number_width, 28))
        if self.playlist.paths:
            self.table.selectRow(max(0, min(selected, len(self.playlist.paths) - 1)))
        self.count.setText(f"Треков: {len(self.playlist.paths)}")
        self.library.clear_button.setEnabled(bool(self.playlist.paths))
        self.library.remove_button.setEnabled(bool(self.playlist.paths))
        self.play_button.setEnabled(bool(self.playlist.paths or self._playing_playlist.paths))
        for button in (self.previous_button, self.next_button):
            button.setEnabled(bool(self._playing_playlist.paths))
        self.library.apply_filter()

    def play(self, index, playlist=None):
        playlist = self.playlist if playlist is None else playlist
        if not 0 <= index < len(playlist.paths):
            return
        path = playlist.paths[index]
        if not path.is_file():
            self.statusBar().showMessage(f"Файл не найден: {path}")
            return
        self._playing_playlist = playlist
        self.collection.playing = self.collection.playlists.index(playlist)
        playlist.current = index
        self._clear_ab()
        self._show_metadata(path)
        self._display_position = 0
        self._display_duration = read_duration_ms(path) or 0
        self._set_remaining_time(True)
        self.wave.set_peaks([])
        self.wave.message = "Строится звуковая волна…"
        self.wave.update()
        self.player.open(path)
        self.wave_service.open(path)
        self._refresh()
        if playlist is self.playlist:
            self.table.selectRow(playlist.current)
        self.statusBar().clearMessage()

    def _toggle(self):
        if self._playing_playlist.current < 0:
            self.play(max(0, self.table.currentRow()))
        else:
            self.player.toggle()

    def _advance(self, direction):
        index = self._playing_playlist.next_index(direction, self.shuffle.isChecked(), repeat=True)
        if index is not None:
            self.play(index, self._playing_playlist)

    def _ended(self):
        if self._ab_start is not None and self._ab_end is not None:
            self.player.media.setPosition(self._ab_start)
            self.player.media.play()
            return
        if self._repeat_mode == "off":
            self._reset_finished_track()
            return
        if self._repeat_mode == "track":
            self.player.media.setPosition(0)
            self.player.media.play()
            return
        index = self._playing_playlist.next_index(
            shuffle=self.shuffle.isChecked(), repeat=self._repeat_mode == "playlist")
        if index is not None:
            self.play(index, self._playing_playlist)
        else:
            self._reset_finished_track()

    def _reset_finished_track(self):
        self.player.media.setPosition(0)
        self._position(0)

    def _remove(self):
        rows = {item.row() for item in self.table.selectedItems() if not self.table.isRowHidden(item.row())}
        self._remove_rows(rows)

    def _clear_playlist(self):
        self._remove_rows(set(range(len(self.playlist.paths))))

    def _remove_rows(self, rows):
        if self.playlist is self._playing_playlist and self.playlist.current in rows:
            self._clear_current_track()
        self.playlist.remove(rows)
        self._refresh()

    def _clear_current_track(self):
        self.player.stop(reload=False)
        self.wave_service.cancel()
        self.wave.set_peaks([])
        self.track_title.setText("Откройте музыку")
        self.library.set_lyrics("")
        self.file_format.setText("Аудиофайл")
        self.sample_rate.setText("")
        self._technical_info = "Аудиофайл"
        self._bitrate_info = ""
        self._notice_changed("")
        self.cover.set_cover(b"")
        self._clear_ab()
        self._position(0)
        self._duration(0)
        self.wave.message = "Добавьте аудиофайлы"

    def _position(self, position):
        if self._ab_end is not None and position >= self._ab_end:
            self.player.media.setPosition(self._ab_start)
            return
        self._display_position = max(0, position)
        self.wave.set_position(position)
        self.elapsed.setText(format_time(position))
        self._update_total_time()

    def _duration(self, duration):
        self._display_duration = max(0, duration)
        self.wave.duration = duration
        self._update_total_time()
        self.wave.update()

    def _toggle_remaining_time(self):
        self._set_remaining_time(not self._show_remaining_time)

    def _set_remaining_time(self, enabled):
        self._show_remaining_time = enabled
        self.total.setProperty("remainingTime", self._show_remaining_time)
        self.total.style().unpolish(self.total)
        self.total.style().polish(self.total)
        self.total.update()
        self._update_total_time()

    def _update_total_time(self):
        if self._show_remaining_time:
            text = format_time(max(0, self._display_duration - self._display_position))
        else:
            text = format_time(self._display_duration)
        self.total.setText(text)
        mode = "Осталось до конца" if self._show_remaining_time else "Продолжительность трека"
        self.total.setAccessibleName(f"{mode}. ЛКМ: текст песни. ПКМ: переключить отображение времени")

    def _state(self, state):
        self.play_button.set_playback_state(
            playing=state == QMediaPlayer.PlaybackState.PlayingState,
            paused=state == QMediaPlayer.PlaybackState.PausedState)

    def _volume(self, value):
        self.player.audio.setVolume(value / 100)
        self.volume.setAccessibleDescription(f"Громкость: {value}%")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_resize_grips()

    def _update_resize_grips(self):
        if hasattr(self, "_left_grip"):
            self._left_grip.setGeometry(0, 0, 8, self.height())
            self._right_grip.setGeometry(self.width() - 8, 0, 8, self.height())
            self._left_grip.raise_()
            self._right_grip.raise_()

    def _wave_failed(self, message):
        self.wave.message = "Звуковая волна недоступна"
        self.wave.update()
        self.statusBar().showMessage(f"Ошибка построения волны: {message}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths(url.toLocalFile() for url in event.mimeData().urls()
                       if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in SUPPORTED)
        event.acceptProposedAction()

    def closeEvent(self, event):
        self.tray.hide()
        QApplication.instance().removeEventFilter(self)
        self.library.close()
        self.preferences.close()
        self.player.stop(reload=False)
        self.wave_service.cancel()
        data = {
            "last_directory": self._dialog_directory(),
            "volume": self.volume.value(), "wheel_step": self.wheel_step.value(),
            "lyrics_font_size": self.library.lyrics_font_size,
            "always_on_top": self._always_on_top,
            "shuffle": self.shuffle.isChecked(), "repeat": self.repeat.isChecked(),
            "repeat_mode": self._repeat_mode,
            **self.collection.serialize(),
            "window": {"geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
                       "position": [self.normalGeometry().x(), self.normalGeometry().y()]
                       if self.isMinimized() else [self.pos().x(), self.pos().y()],
                       "available_geometry": list(self.screen().availableGeometry().getRect()),
                       "layout_version": 2},
        }
        try:
            self.store.save(data)
        except OSError as error:
            import logging
            logging.exception("Не удалось сохранить настройки: %s", error)
        event.accept()
