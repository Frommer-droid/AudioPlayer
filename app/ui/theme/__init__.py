"""Общая тёмная тема."""
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QProxyStyle, QStyle

from app.ui.theme.colors import THEME_COLORS as C


class NoFocusFrameStyle(QProxyStyle):
    """Фокус и клавиатура работают, но системная рамка не рисуется."""

    def drawPrimitive(self, element, option, painter, widget=None):
        if element != QStyle.PrimitiveElement.PE_FrameFocusRect:
            super().drawPrimitive(element, option, painter, widget)


def apply_theme(app):
    app.setStyle(NoFocusFrameStyle("Fusion"))
    app.setFont(QFont("Segoe UI", 9))
    palette = QPalette()
    for role, token in {
        QPalette.ColorRole.Window: "background", QPalette.ColorRole.WindowText: "text_strong",
        QPalette.ColorRole.Base: "surface", QPalette.ColorRole.AlternateBase: "alternate",
        QPalette.ColorRole.Text: "text_strong", QPalette.ColorRole.Button: "surface_hover",
        QPalette.ColorRole.ButtonText: "text_strong", QPalette.ColorRole.Highlight: "selection",
        QPalette.ColorRole.HighlightedText: "text_strong", QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text_strong",
    }.items():
        palette.setColor(role, QColor(C[token]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(C["disabled_text"]))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QWidget {{ background: {C['background']}; color: {C['text_strong']}; }}
        QWidget#playerShell {{ border: 1px solid {C['accent']}; border-radius: 7px; }}
        QWidget#playerShell[playlistAttached="true"] {{
            border-bottom-left-radius: 0; border-bottom-right-radius: 0; }}
        QDialog#playlistPanel {{ border: 1px solid {C['accent']};
            border-bottom-left-radius: 7px; border-bottom-right-radius: 7px; }}
        QWidget#resizeGrip {{ background: transparent; border: 0; }}
        QMainWindow, QTabWidget::pane {{ background: {C['background']}; border: 0; }}
        QLabel#muted {{ color: {C['muted']}; }}
        QLabel#title {{ font-size: 17px; font-weight: 500; }}
        QLabel#brand {{ font-size: 17px; font-weight: 600; }}
        QLabel#brandMark {{ font-size: 22px; color: {C['accent']}; }}
        QLabel#artist {{ font-size: 12px; }}
        QLabel#technical, QLabel#time {{ font-size: 10px; }}
        QLabel#time {{ font-family: Consolas; font-size: 20px; }}
        QLabel#time[remainingTime="true"] {{ color: {C['danger']}; }}
        QPushButton {{ background: {C['surface_hover']}; border: 1px solid {C['border']};
            border-radius: 7px; padding: 8px 13px; min-height: 22px; }}
        QPushButton:hover {{ background: {C['primary_hover']}; }}
        QPushButton:pressed {{ background: {C['surface_pressed']}; }}
        QPushButton:checked {{ color: {C['accent']}; border-color: {C['accent']}; }}
        QPushButton:disabled {{ color: {C['disabled_text']}; background: {C['disabled_background']}; }}
        QAbstractItemView {{ outline: 0; }}
        QPushButton#primaryButton {{ background: {C['accent']}; color: {C['on_accent']}; }}
        QPushButton#primaryButton:hover {{ background: {C['accent_hover']}; }}
        QPushButton#primaryButton:pressed {{ background: {C['accent_pressed']}; }}
        QTableWidget {{ background: {C['surface']}; alternate-background-color: {C['alternate']};
            selection-background-color: {C['selection']}; border: 1px solid {C['border']};
            gridline-color: {C['surface']}; }}
        QTableWidget::item {{ padding: 9px; }}
        QTableWidget::item:selected {{ background: {C['selection']}; color: {C['accent']}; }}
        QHeaderView::section {{ background: {C['surface_alt']}; color: {C['muted']};
            border: 0; padding: 10px; text-align: left; }}
        QTabBar::tab {{ background: {C['surface']}; padding: 12px 20px; color: {C['muted']}; }}
        QTabBar::tab:selected {{ color: {C['accent']}; background: {C['background']}; }}
        QTabBar::tab:hover {{ color: {C['text_strong']}; }}
        QTabBar#libraryTabs, QPushButton#playlistAction,
        QLabel#playlistCount, QLabel#lyricsFontValue,
        QTableWidget#playlistTable, QHeaderView#playlistTableHeader {{ font-size: 17px; }}
        QHeaderView#playlistTableHeader::section {{ padding: 4px 8px; font-weight: 400; }}
        QTableWidget#playlistTable::item {{ padding: 4px 8px; }}
        QWidget#playlistFooter {{ background: {C['surface_alt']}; border: 0; }}
        QWidget#playlistFooter QLabel, QWidget#playlistFooter QToolButton {{
            background: {C['surface_alt']}; border: 0; }}
        QPushButton#playlistAction {{ background: {C['surface_alt']}; border: 0;
            border-radius: 4px; padding: 0; min-height: 0; }}
        QPushButton#playlistAction:hover {{ background: {C['surface_hover']}; }}
        QPushButton#playlistAction:pressed {{ background: {C['surface_pressed']}; }}
        QLineEdit#playlistSearch {{ background: {C['surface_alt']}; color: {C['text_strong']};
            border: 0; padding: 0 4px; font-size: 17px; }}
        QTabBar#libraryTabs::tab {{ padding: 6px 12px; border-bottom: 2px solid transparent; }}
        QTabBar#libraryTabs::tab:selected {{ border-bottom-color: {C['accent']}; }}
        QWidget#lyricsPage {{ background: {C['surface']}; border: 1px solid {C['border']}; }}
        QPlainTextEdit#lyricsText {{ background: {C['surface']}; border: 0;
            padding: 12px; }}
        QSlider::groove:horizontal {{ height: 3px; background: {C['border']}; }}
        QSlider::sub-page:horizontal {{ background: {C['accent']}; }}
        QSlider::handle:horizontal {{ background: {C['accent']}; width: 12px; margin: -5px 0;
            border-radius: 6px; }}
        QSlider::handle:horizontal:hover {{ background: {C['accent_hover']}; }}
        QSpinBox {{ background: {C['surface']}; padding: 8px; border: 1px solid {C['border']}; }}
        QWidget#settingsShell {{ border: 1px solid {C['border']}; border-radius: 10px; }}
        QLabel#settingsHeading {{ font-size: 16px; font-weight: 600; }}
        QLabel#settingsHint {{ color: {C['muted']}; font-size: 11px; }}
        QSpinBox#wheelStep {{ background: {C['surface']}; border: 0; border-radius: 6px;
            padding: 0; font-size: 14px; color: {C['accent']}; }}
        QSpinBox#wheelStep QLineEdit {{ background: transparent; border: 0; padding: 0; }}
        QToolTip {{ background: {C['surface']}; color: {C['text_strong']}; border: 1px solid {C['border']}; }}
        QStatusBar {{ color: {C['muted']}; }}
    """)
