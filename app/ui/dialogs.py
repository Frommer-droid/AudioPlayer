"""Пристыковываемый плейлист и отдельное окно настроек."""
from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabBar,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.controls import IconButton, SideGrip, TitleBar
from app.ui.icon_assets import button_icon
from app.ui.theme.colors import THEME_COLORS as C


class _PlaylistTitleBar(TitleBar):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().detach()
        super().mousePressEvent(event)


class _PlaylistTabs(QTabBar):
    closeRequested = Signal(int)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._close_index = self.tabAt(event.position().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0 and index == getattr(self, "_close_index", -1):
                self.closeRequested.emit(index)
            self._close_index = -1
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        event.accept()


class _PlaylistResizeGrip(SideGrip):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.edge != Qt.Edge.BottomEdge:
            self.window().detach()
        super().mousePressEvent(event)


class PlaylistDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.NoDropShadowWindowHint)
        self._owner = owner
        self._docked = True
        self._syncing = False
        self._wanted_visible = False
        self._suspended = False
        self.setObjectName("playlistPanel")
        self.setWindowTitle("Плейлист — AudioPlayer")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumSize(360, 200)
        self.resize(owner.width(), 420)
        self.setSizeGripEnabled(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 12)
        layout.setSpacing(6)
        header = _PlaylistTitleBar()
        header.setFixedHeight(34)
        header.setAccessibleDescription("Перетащите, чтобы отстыковать плейлист")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = _PlaylistTabs()
        self.tabs.closeRequested.connect(owner._close_playlist)
        self.tabs.setObjectName("libraryTabs")
        self.tabs.setAccessibleName("Плейлисты")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setMinimumWidth(60)
        for playlist in owner.collection.playlists:
            self.tabs.addTab(playlist.name)
        self.tabs.setCurrentIndex(owner.collection.active)
        header_layout.addWidget(self.tabs, 1)
        self.add_playlist_button = IconButton("increase", "Добавление плейлиста", owner._add_playlist, 28)
        header_layout.addWidget(self.add_playlist_button)
        self.lyrics_font_controls = QWidget()
        font_layout = QHBoxLayout(self.lyrics_font_controls)
        font_layout.setContentsMargins(4, 0, 0, 0)
        font_layout.setSpacing(2)
        self.lyrics_font_decrease = IconButton(
            "decrease", "Уменьшить шрифт текста песни", lambda: self._set_lyrics_font_size(
                self.lyrics_font_size - 1), 28)
        self.lyrics_font_value = QLabel()
        self.lyrics_font_value.setObjectName("lyricsFontValue")
        self.lyrics_font_value.setFixedWidth(26)
        self.lyrics_font_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lyrics_font_increase = IconButton(
            "increase", "Увеличить шрифт текста песни", lambda: self._set_lyrics_font_size(
                self.lyrics_font_size + 1), 28)
        for widget in (self.lyrics_font_decrease, self.lyrics_font_value, self.lyrics_font_increase):
            font_layout.addWidget(widget)
        self.lyrics_font_controls.hide()
        self.lyrics_button = IconButton("lyrics", "Текст песни", self._toggle_lyrics, 28)
        self.lyrics_button.setCheckable(True)
        self.lyrics_button.hide()
        header_layout.addWidget(self.lyrics_button)
        self.close_button = IconButton("close", "Скрыть плейлист", self.hide_panel, 26)
        header_layout.addWidget(self.close_button)
        layout.addWidget(header)
        self.pages = QStackedWidget()
        playlist_page = QWidget()
        playlist_layout = QVBoxLayout(playlist_page)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        playlist_layout.setSpacing(6)
        self.playlist_footer = QWidget()
        self.playlist_footer.setObjectName("playlistFooter")
        toolbar = QHBoxLayout(self.playlist_footer)
        toolbar.setContentsMargins(6, 0, 2, 0)
        toolbar.setSpacing(4)
        for name, label, symbol, callback in (
                ("add_files_button", "Добавить файлы", "add_files", owner._add_files),
                ("add_folder_button", "Папка", "add_folder", owner._add_folder),
                ("remove_button", "Убрать", "min", owner._remove),
                ("clear_button", "Убрать всё", "clear_playlist", owner._clear_playlist)):
            button = QPushButton()
            button.setObjectName("playlistAction")
            button.setAccessibleName(label)
            button.setFixedSize(44, 36)
            button.setIcon(button_icon(symbol, C["text_strong"]))
            button.setIconSize(QSize(20, 20))
            button.setAccessibleDescription("Убрать все записи из плейлиста. Файлы останутся на диске"
                              if name == "clear_button" else label)
            button.clicked.connect(callback)
            setattr(self, name, button)
        self.count = QLabel()
        self.count.setObjectName("playlistCount")
        self.search = QLineEdit()
        self.search.setObjectName("playlistSearch")
        self.search.setAccessibleName("Поиск трека по названию")
        self.search.setPlaceholderText("Поиск по названию…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(36)
        self.search.setMinimumWidth(100)
        self.search.addAction(button_icon("search", C["muted"]), QLineEdit.ActionPosition.LeadingPosition)
        toolbar.addWidget(self.search, 1)
        toolbar.addSpacing(16)
        toolbar.addWidget(self.count)
        toolbar.addSpacing(12)
        for button in (self.add_files_button, self.add_folder_button, self.remove_button, self.clear_button):
            toolbar.addWidget(button)
        self.table = QTableWidget(0, 4)
        self.table.setObjectName("playlistTable")
        self.table.horizontalHeader().setObjectName("playlistTableHeader")
        self.table.setHorizontalHeaderLabels(["№", "Название", "Формат", "Время"])
        for column in range(4):
            alignment = Qt.AlignmentFlag.AlignLeft if column == 1 else Qt.AlignmentFlag.AlignHCenter
            self.table.horizontalHeaderItem(column).setTextAlignment(
                alignment | Qt.AlignmentFlag.AlignVCenter)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setResizeContentsPrecision(-1)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().sectionClicked.connect(owner._sort_playlist)
        for column in (0, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Плейлист")
        self.table.cellDoubleClicked.connect(lambda row, _column: owner.play(row))
        self.table.itemSelectionChanged.connect(self._update_remove_button)
        self.search.textChanged.connect(self.apply_filter)
        playlist_layout.addWidget(self.table, 1)
        playlist_layout.addWidget(self.playlist_footer)
        self.pages.addWidget(playlist_page)
        self.lyrics_page = QWidget()
        self.lyrics_page.setObjectName("lyricsPage")
        lyrics_layout = QVBoxLayout(self.lyrics_page)
        lyrics_layout.setContentsMargins(1, 4, 1, 1)
        lyrics_layout.setSpacing(0)
        self.lyrics_text = QPlainTextEdit()
        self.lyrics_text.setObjectName("lyricsText")
        self.lyrics_text.setAccessibleName("Текст песни")
        self.lyrics_text.setReadOnly(True)
        self._set_lyrics_font_size(owner.saved.get("lyrics_font_size", 14))
        lyrics_layout.addWidget(self.lyrics_text, 1)
        lyrics_layout.addWidget(self.lyrics_font_controls, 0, Qt.AlignmentFlag.AlignRight)
        self.pages.addWidget(self.lyrics_page)
        self.tabs.currentChanged.connect(owner._select_playlist)
        self.tabs.tabBarClicked.connect(lambda _index: self.show_playlist())
        layout.addWidget(self.pages)
        self._resize_grips = {}
        for name, edges in (
                ("top", Qt.Edge.TopEdge), ("bottom", Qt.Edge.BottomEdge),
                ("left", Qt.Edge.LeftEdge), ("right", Qt.Edge.RightEdge),
                ("top_left", Qt.Edge.TopEdge | Qt.Edge.LeftEdge),
                ("top_right", Qt.Edge.TopEdge | Qt.Edge.RightEdge),
                ("bottom_left", Qt.Edge.BottomEdge | Qt.Edge.LeftEdge),
                ("bottom_right", Qt.Edge.BottomEdge | Qt.Edge.RightEdge)):
            grip = _PlaylistResizeGrip(self, edges)
            self._resize_grips[name] = grip
            setattr(self, f"_{name}_grip", grip)
        self._update_resize_grips()
        owner.installEventFilter(self)

    def _update_remove_button(self):
        self.remove_button.setEnabled(any(not self.table.isRowHidden(item.row())
                                          for item in self.table.selectedItems()))

    def apply_filter(self):
        query = self.search.text().strip().casefold()
        visible = 0
        total = self.table.rowCount()
        for row in range(total):
            item = self.table.item(row, 1)
            matches = not query or (item is not None and query in item.text().casefold())
            self.table.setRowHidden(row, not matches)
            if matches:
                visible += 1
            else:
                for column in range(self.table.columnCount()):
                    cell = self.table.item(row, column)
                    if cell is not None:
                        cell.setSelected(False)
        self.count.setText(f"Найдено: {visible} / {total}" if query else f"Треков: {total}")
        # Reserve the largest counter for this queue, including digit changes.
        digits = max(4, len(str(total)))
        self.count.ensurePolished()
        metrics = self.count.fontMetrics()
        digit = max("0123456789", key=metrics.horizontalAdvance)
        counter = f"Найдено: {digit * digits} / {digit * digits}"
        self.count.setFixedWidth(metrics.horizontalAdvance(counter) + 16)
        self._update_remove_button()

    def _set_lyrics_font_size(self, value):
        try:
            size = int(value) if not isinstance(value, bool) else 14
        except (ValueError, TypeError, OverflowError):
            size = 14
        self.lyrics_font_size = max(10, min(32, size))
        font = self.lyrics_text.font()
        font.setPixelSize(self.lyrics_font_size)
        self.lyrics_text.setFont(font)
        self.lyrics_text.document().setDefaultFont(font)
        self.lyrics_font_value.setText(str(self.lyrics_font_size))
        self.lyrics_font_value.setAccessibleDescription(f"Размер шрифта: {self.lyrics_font_size} пикс.")
        self.lyrics_font_decrease.setEnabled(self.lyrics_font_size > 10)
        self.lyrics_font_increase.setEnabled(self.lyrics_font_size < 32)

    def set_lyrics(self, text):
        text = text.strip()
        self.lyrics_text.setPlainText(text)
        if not text:
            self.show_playlist()
        self.lyrics_button.setVisible(bool(text))
        self._owner.total.setCursor(Qt.CursorShape.PointingHandCursor if text else Qt.CursorShape.ArrowCursor)

    def show_playlist(self):
        self.pages.setCurrentIndex(0)
        self.lyrics_button.setChecked(False)
        self.lyrics_font_controls.hide()

    def show_lyrics(self):
        if self.lyrics_text.toPlainText().strip():
            self.pages.setCurrentIndex(1)
            self.lyrics_button.setChecked(True)
            self.lyrics_font_controls.show()

    def _toggle_lyrics(self):
        if self.lyrics_button.isChecked():
            self.show_lyrics()
        else:
            self.show_playlist()

    def _update_resize_grips(self):
        if not hasattr(self, "_resize_grips"):
            return
        width, height, corner, edge = self.width(), self.height(), 12, 8
        geometry = {
            "top": (corner, 0, width - 2 * corner, 6),
            "bottom": (corner, height - edge, width - 2 * corner, edge),
            "left": (0, corner, edge, height - 2 * corner),
            "right": (width - edge, corner, edge, height - 2 * corner),
            "top_left": (0, 0, corner, corner),
            "top_right": (width - corner, 0, corner, corner),
            "bottom_left": (0, height - corner, corner, corner),
            "bottom_right": (width - corner, height - corner, corner, corner),
        }
        for name, grip in self._resize_grips.items():
            grip.setGeometry(*geometry[name])
            grip.raise_()

    @property
    def docked(self):
        return self._docked

    def _update_join(self):
        shell = self._owner.centralWidget()
        joined = self._docked and self.isVisible() and not self._suspended
        if shell.property("playlistAttached") != joined:
            shell.setProperty("playlistAttached", joined)
            shell.style().unpolish(shell)
            shell.style().polish(shell)
            shell.update()

    def _sync_to_owner(self):
        if not self._docked:
            return
        self._syncing = True
        try:
            anchor = self._owner.frameGeometry().bottomLeft() + QPoint(0, 1)
            self.resize(self._owner.frameGeometry().width(), self.height())
            self.move(anchor)
        finally:
            self._syncing = False

    def show_docked(self):
        self._docked = True
        self._wanted_visible = True
        self._suspended = False
        self._sync_to_owner()
        self._syncing = True
        try:
            self.show()
        finally:
            self._syncing = False
        self._sync_to_owner()
        self._update_join()

    def hide_panel(self):
        self._wanted_visible = False
        self.hide()
        self._update_join()

    def detach(self):
        self._docked = False
        self._update_join()

    def _suspend_with_owner(self):
        self._suspended = True
        self.hide()
        self._update_join()

    def _resume_with_owner(self):
        if not self._owner.isVisible() or self._owner.isMinimized():
            return
        self._suspended = False
        if self._wanted_visible:
            self._syncing = True
            try:
                self.show()
            finally:
                self._syncing = False
            self._sync_to_owner()
        self._update_join()

    def eventFilter(self, watched, event):
        if watched is self._owner:
            kind = event.type()
            if kind in (QEvent.Type.Move, QEvent.Type.Resize):
                if self.isVisible():
                    self._sync_to_owner()
            elif kind == QEvent.Type.Hide:
                self._suspend_with_owner()
            elif kind == QEvent.Type.Show:
                QTimer.singleShot(0, self._resume_with_owner)
            elif kind == QEvent.Type.WindowStateChange:
                if self._owner.isMinimized():
                    self._suspend_with_owner()
                else:
                    QTimer.singleShot(0, self._resume_with_owner)
        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.isVisible() and self._docked and not self._syncing:
            anchor = self._owner.frameGeometry().bottomLeft() + QPoint(0, 1)
            if self.pos() != anchor:
                self.detach()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_resize_grips()
        if self.isVisible() and self._docked and not self._syncing:
            if self.width() != self._owner.frameGeometry().width():
                self.detach()

    def hideEvent(self, event):
        if not self._suspended and self._owner.isVisible() and not self._owner.isMinimized():
            self._wanted_visible = False
        super().hideEvent(event)
        self._update_join()

    def closeEvent(self, event):
        self._wanted_visible = False
        super().closeEvent(event)


class _WheelStepBox(QSpinBox):
    """Без native arrows: Qt/QSS иногда оставляет edit-field шириной 1 px."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.lineEdit().setGeometry(self.rect().adjusted(3, 0, -3, 0))


class SettingsDialog(QDialog):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Настройки — AudioPlayer")
        self.setObjectName("settingsPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(430)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        shell = QWidget()
        shell.setObjectName("settingsShell")
        outer.addWidget(shell)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(20, 14, 20, 20)
        layout.setSpacing(18)
        header = TitleBar()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        symbol = QLabel()
        symbol.setPixmap(button_icon("settings", C["accent"]).pixmap(22, 22))
        header_layout.addWidget(symbol)
        heading = QLabel("Настройки")
        heading.setObjectName("settingsHeading")
        header_layout.addWidget(heading)
        header_layout.addStretch()
        header_layout.addWidget(IconButton("close", "Закрыть настройки", self.close, 28))
        layout.addWidget(header)
        row = QHBoxLayout()
        labels = QVBoxLayout()
        labels.setSpacing(3)
        labels.addWidget(QLabel("Шаг перемотки"))
        subtitle = QLabel("Колесо над звуковой волной")
        subtitle.setObjectName("settingsHint")
        labels.addWidget(subtitle)
        row.addLayout(labels)
        row.addStretch()
        self.wheel_step = _WheelStepBox()
        self.wheel_step.setObjectName("wheelStep")
        self.wheel_step.setRange(1, 60)
        self.wheel_step.setSuffix(" сек.")
        self.wheel_step.setValue(5)
        self.wheel_step.setAccessibleName("Шаг перемотки в секундах")
        self.wheel_step.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.wheel_step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wheel_step.setKeyboardTracking(False)
        self.wheel_step.setFixedSize(68, 36)
        self.decrease = IconButton("decrease", "Уменьшить шаг", self.wheel_step.stepDown, 30)
        self.increase = IconButton("increase", "Увеличить шаг", self.wheel_step.stepUp, 30)
        row.setSpacing(3)
        for widget in (self.decrease, self.wheel_step, self.increase):
            row.addWidget(widget)
        layout.addLayout(row)
        directions = QVBoxLayout()
        directions.setSpacing(12)
        for icon, gesture, action in (("arrow_down", "На себя", "Вперёд по треку"),
                                      ("arrow_up", "От себя", "Назад по треку")):
            direction = QHBoxLayout()
            direction.setSpacing(10)
            glyph = QLabel()
            glyph.setPixmap(button_icon(icon, C["muted"]).pixmap(18, 18))
            direction.addWidget(glyph)
            label = QLabel(gesture)
            label.setFixedWidth(100)
            direction.addWidget(label)
            direction.addWidget(QLabel(action), 1)
            directions.addLayout(direction)
        layout.addLayout(directions)
        hint = QLabel("Вне волны колесо регулирует громкость")
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)
        self.wheel_step.valueChanged.connect(self._step_changed)
        self._step_changed(self.wheel_step.value())

    def _step_changed(self, value):
        self.decrease.setEnabled(value > self.wheel_step.minimum())
        self.increase.setEnabled(value < self.wheel_step.maximum())
