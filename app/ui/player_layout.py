"""Горизонтальная компоновка по предоставленному владельцем образцу."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QSlider, QVBoxLayout, QWidget

from app.ui.controls import (
    CoverButton,
    DurationLabel,
    ElidedLabel,
    IconButton,
    LogoButton,
    TitleBar,
    TransportButton,
)
from app.ui.dialogs import PlaylistDialog, SettingsDialog
from app.ui.waveform import WaveformWidget

PLAYER_HEIGHT = 147
CONTROL_BUTTON_SIZE = 34
CONTROL_SPACING = 8
GROUP_SPACING = 20
PLAYER_MARGIN = 10
TRACK_INFO_MAX_WIDTH = 75


def build_player(window):
    shell = QWidget()
    shell.setObjectName("playerShell")
    window.setCentralWidget(shell)
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(PLAYER_MARGIN, 5, PLAYER_MARGIN, 6)
    layout.setSpacing(0)

    header = TitleBar()
    header.setFixedHeight(22)
    title_layout = QGridLayout(header)
    title_layout.setContentsMargins(0, 0, 0, 0)
    title_layout.setSpacing(5)
    left = QHBoxLayout()
    left.setSpacing(5)
    mark = LogoButton(window._toggle_on_top)
    window.brand_mark = mark
    mark.setObjectName("brandMark")
    left.addWidget(mark)
    window.menu_button = IconButton("menu", "Меню", window._show_menu, 24)
    left.addWidget(window.menu_button)
    left.addStretch()
    window.track_title = ElidedLabel("Откройте музыку")
    window.track_title.setObjectName("title")
    window.track_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.track_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    right = QHBoxLayout()
    right.setSpacing(5)
    right.addWidget(IconButton("min", "Свернуть", window.showMinimized, 28))
    right.addWidget(IconButton("close", "Закрыть", window.close, 28))
    title_layout.setColumnStretch(1, 1)
    title_layout.addLayout(left, 0, 0)
    title_layout.addWidget(window.track_title, 0, 1)
    title_layout.addLayout(right, 0, 2)
    side_width = max(left.sizeHint().width(), right.sizeHint().width())
    title_layout.setColumnMinimumWidth(0, side_width)
    title_layout.setColumnMinimumWidth(2, side_width)
    layout.addWidget(header)

    body = QGridLayout()
    body.setContentsMargins(0, 4, 0, 2)
    body.setSpacing(8)
    metadata = QHBoxLayout()
    metadata.setContentsMargins(0, 0, 0, 0)
    metadata.setSpacing(8)
    window.cover = CoverButton(window._open_files)
    metadata.addWidget(window.cover)

    info = QWidget()
    info.setFixedWidth(TRACK_INFO_MAX_WIDTH)
    info_layout = QVBoxLayout(info)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(1)
    window.file_format = ElidedLabel("Аудиофайл")
    window.file_format.setObjectName("artist")
    window.file_format.setFixedHeight(19)
    window.sample_rate = ElidedLabel("")
    window.sample_rate.setObjectName("muted")
    window.sample_rate.setFixedHeight(18)
    window.track_info = ElidedLabel("")
    window.track_info.setObjectName("technical")
    window.track_info.setFixedHeight(18)
    for label in (window.file_format, window.sample_rate, window.track_info):
        info_layout.addWidget(label)
    info_layout.addStretch()
    metadata.addWidget(info, 1)
    metadata.addStretch()

    window.previous_button = IconButton("previous", "Предыдущий трек", lambda: window._advance(-1),
                                        CONTROL_BUTTON_SIZE)
    window.play_button = TransportButton(window._toggle, window.player.stop)
    window.next_button = IconButton("next", "Следующий трек", lambda: window._advance(1), CONTROL_BUTTON_SIZE)
    window.repeat = IconButton("repeat", "Повтор выключен", window._cycle_repeat, CONTROL_BUTTON_SIZE)
    window.repeat.setCheckable(True)
    window.ab_button = IconButton("ab", "Повтор фрагмента: поставить точку A", window._mark_ab,
                                 CONTROL_BUTTON_SIZE)
    window.ab_button.setCheckable(True)
    window.shuffle = IconButton("shuffle", "Случайный порядок", lambda: None, CONTROL_BUTTON_SIZE)
    window.shuffle.setCheckable(True)
    window.mute_button = IconButton("speaker", "Выключить звук", window._mute, CONTROL_BUTTON_SIZE)
    window.mute_button.setCheckable(True)
    window.volume = QSlider(Qt.Orientation.Horizontal)
    window.volume.setAccessibleName("Громкость")
    window.volume.setRange(0, 100)
    window.volume.setValue(65)
    window.settings_button = IconButton("settings", "Настройки", window._show_settings, CONTROL_BUTTON_SIZE)
    groups = []
    for widgets in ((window.repeat, window.ab_button, window.shuffle),
                    (window.mute_button, window.volume)):
        group = QHBoxLayout()
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(CONTROL_SPACING)
        for widget in widgets:
            group.addWidget(widget)
        groups.append(group)
    before_play = QHBoxLayout()
    before_play.setContentsMargins(0, 0, 0, 0)
    before_play.setSpacing(0)
    before_play.addLayout(metadata)
    before_play.addSpacing(CONTROL_SPACING)
    before_play.addStretch()
    before_play.addLayout(groups[0])
    before_play.addSpacing(GROUP_SPACING)
    before_play.addWidget(window.previous_button)
    after_play = QHBoxLayout()
    after_play.setContentsMargins(0, 0, 0, 0)
    after_play.setSpacing(0)
    after_play.addWidget(window.next_button)
    after_play.addSpacing(GROUP_SPACING)
    after_play.addLayout(groups[1])
    after_play.addSpacing(GROUP_SPACING)
    after_play.addWidget(window.settings_button)
    after_play.addStretch()
    body.addLayout(before_play, 0, 0)
    body.addWidget(window.play_button, 0, 1)
    body.addLayout(after_play, 0, 2)
    body.setColumnStretch(0, 1)
    body.setColumnStretch(2, 1)
    layout.addLayout(body)
    window._body_balance = (info, body, before_play, after_play, groups[0])
    for label in (window.file_format, window.sample_rate, window.track_info):
        label.textChanged.connect(lambda: balance_player(window))
    balance_player(window)

    window.wave = WaveformWidget()
    timeline = QHBoxLayout()
    timeline.setContentsMargins(1, 0, 1, 0)
    timeline.setSpacing(3)
    window.elapsed = DurationLabel("00:00")
    window.elapsed.setAccessibleName("Прошедшее время. Показать или скрыть плейлист")
    window.elapsed.setCursor(Qt.CursorShape.PointingHandCursor)
    window.elapsed.clicked.connect(window._toggle_playlist)
    window.total = DurationLabel("00:00")
    window.total.setAccessibleName("Продолжительность трека. Открыть текст песни")
    window.total.clicked.connect(window._toggle_lyrics)
    window.total.rightClicked.connect(window._toggle_remaining_time)
    for label in (window.elapsed, window.total):
        label.setObjectName("time")
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        label.setFixedWidth(62)
        label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    window.total.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
    timeline.addWidget(window.elapsed)
    timeline.addWidget(window.wave, 1)
    timeline.addWidget(window.total)
    layout.addLayout(timeline, 1)

    window.library = PlaylistDialog(window)
    window.table = window.library.table
    window.count = window.library.count
    window.preferences = SettingsDialog(window)
    window.wheel_step = window.preferences.wheel_step
    window.statusBar().hide()


def balance_player(window):
    info, body, before_play, after_play, repeat_group = window._body_balance
    labels = (window.file_format, window.sample_rate, window.track_info)
    for label in labels:
        label.ensurePolished()
    text_width = max(label.fontMetrics().horizontalAdvance(label.text()) for label in labels)
    info.setFixedWidth(min(TRACK_INFO_MAX_WIDTH, max(1, text_width)))
    # Equal outer gaps require right reach - left reach = metadata's right x.
    # Play remains on the central grid axis; only the useful slider length changes.
    play_half = window.play_button.width() / 2
    left_reach = (play_half + CONTROL_SPACING + window.previous_button.width()
                  + GROUP_SPACING + repeat_group.minimumSize().width())
    right_without_slider = (play_half + CONTROL_SPACING + window.next_button.width()
                            + GROUP_SPACING + window.mute_button.width() + CONTROL_SPACING
                            + GROUP_SPACING + window.settings_button.width())
    visible_width = max(label.fontMetrics().tightBoundingRect(
        label.fontMetrics().elidedText(label.text(), Qt.TextElideMode.ElideRight, info.width())
    ).right() + 1 for label in labels if label.text()) if any(label.text() for label in labels) else 0
    metadata_right = PLAYER_MARGIN + window.cover.width() + CONTROL_SPACING + visible_width
    # Repeat's SVG ink starts at x=3, settings at x=2 in a 24px viewBox,
    # both rendered at 22px. Match painted edges rather than button rectangles.
    icon_inset_difference = (2 - 3) * 22 / 24
    window.volume.setFixedWidth(round(
        metadata_right + left_reach - right_without_slider + icon_inset_difference))
    side_minimum = max(before_play.minimumSize().width(), after_play.minimumSize().width())
    body.setColumnMinimumWidth(0, side_minimum)
    body.setColumnMinimumWidth(2, side_minimum)
    window.centralWidget().layout().invalidate()
    window.setMinimumWidth(window.centralWidget().minimumSizeHint().width())
