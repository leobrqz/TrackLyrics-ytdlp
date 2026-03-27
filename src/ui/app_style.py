"""
Palette-driven application stylesheet (same pattern as ShScriptHub theme.py).
Applied on QApplication so every widget stays consistent in light and dark mode.
"""

from __future__ import annotations

DARK_PALETTE = {
    "bg_main": "#0d0f12",
    "bg_elevated": "#14161a",
    "bg_card": "#1a1d22",
    "border": "#2a2e36",
    "text_primary": "#e8eaed",
    "text_secondary": "#9aa0a8",
    "text_muted": "#6b7280",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_pressed": "#1d4ed8",
    "selection_bg": "#1e3a5f",
    "selection_fg": "#e8eaed",
    "hover_list": "#22262e",
    "menu_bg": "#1a1d22",
    "menu_hover": "#2a2e36",
    "scrollbar_track": "#14161a",
    "scrollbar_handle": "#3f4654",
    "scrollbar_handle_hover": "#525a6a",
    "player_border": "#2a2e36",
    "tab_selected": "#1e3a5f",
    "status_bg": "#14161a",
}

LIGHT_PALETTE = {
    "bg_main": "#f0f2f5",
    "bg_elevated": "#ffffff",
    "bg_card": "#ffffff",
    "border": "#d8dde6",
    "text_primary": "#1a1d24",
    "text_secondary": "#4b5563",
    "text_muted": "#6b7280",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "accent_pressed": "#1e40af",
    "selection_bg": "#dbeafe",
    "selection_fg": "#1e3a8a",
    "hover_list": "#f3f4f6",
    "menu_bg": "#ffffff",
    "menu_hover": "#e5e7eb",
    "scrollbar_track": "#e8eaef",
    "scrollbar_handle": "#b8c0cc",
    "scrollbar_handle_hover": "#9ca3af",
    "player_border": "#d8dde6",
    "tab_selected": "#ffffff",
    "status_bg": "#ffffff",
}


def get_stylesheet(theme: str) -> str:
    if theme not in ("dark", "light"):
        theme = "dark"
    p = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
    return f"""
QApplication, QMainWindow {{
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 10pt;
}}
QMainWindow {{
    background-color: {p["bg_main"]};
}}
QWidget#centralRoot {{
    background-color: {p["bg_main"]};
}}
QSplitter#mainSplitter {{
    background-color: {p["bg_main"]};
}}
QLabel {{
    color: {p["text_secondary"]};
}}
QToolBar#mainToolbar {{
    background-color: {p["bg_elevated"]};
    border: none;
    border-bottom: 1px solid {p["border"]};
    padding: 2px 10px;
    spacing: 6px;
}}
QToolBar#mainToolbar QPushButton#toolbarPrimaryBtn {{
    background-color: {p["accent"]};
    color: #ffffff;
    border: none;
    border-radius: 5px;
    padding: 4px 14px;
    font-weight: 600;
    min-width: 0;
}}
QToolBar#mainToolbar QPushButton#toolbarPrimaryBtn:hover {{
    background-color: {p["accent_hover"]};
}}
QToolBar#mainToolbar QPushButton#toolbarPrimaryBtn:pressed {{
    background-color: {p["accent_pressed"]};
}}
QToolBar#mainToolbar QPushButton#toolbarTextBtn {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: none;
    border-radius: 4px;
    padding: 2px 8px;
    font-weight: 500;
    min-width: 0;
}}
QToolBar#mainToolbar QPushButton#toolbarTextBtn:hover {{
    background-color: {p["menu_hover"]};
    color: {p["text_primary"]};
}}
QAbstractItemView {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    color: {p["text_primary"]};
    padding: 4px;
    outline: none;
    selection-background-color: {p["selection_bg"]};
    selection-color: {p["selection_fg"]};
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background-color: {p["hover_list"]};
}}
QListWidget::item:selected {{
    background-color: {p["selection_bg"]};
    color: {p["selection_fg"]};
}}
QLineEdit {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {p["accent"]};
    selection-color: #ffffff;
}}
QLineEdit:focus {{
    border-color: {p["accent"]};
}}
QWidget#lyricsModeRow {{
    background-color: transparent;
}}
QToolButton#lyricsTabBtnFirst,
QToolButton#lyricsTabBtnSecond {{
    background-color: {p["bg_elevated"]};
    color: {p["text_muted"]};
    padding: 4px 12px;
    min-height: 22px;
    font-size: 9pt;
    border: 1px solid {p["border"]};
    border-bottom: none;
}}
QToolButton#lyricsTabBtnFirst {{
    border-top-left-radius: 4px;
    border-right: none;
}}
QToolButton#lyricsTabBtnSecond {{
    border-top-right-radius: 4px;
}}
QToolButton#lyricsTabBtnFirst:checked,
QToolButton#lyricsTabBtnSecond:checked {{
    background-color: {p["tab_selected"]};
    color: {p["accent"]};
    font-weight: 600;
}}
QStackedWidget#lyricsStack {{
    border: 1px solid {p["border"]};
    border-top: none;
    border-radius: 0 0 6px 6px;
    background-color: {p["bg_card"]};
}}
QProgressBar {{
    background-color: {p["bg_card"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    text-align: center;
    color: {p["text_primary"]};
    min-height: 16px;
}}
QProgressBar::chunk {{
    background-color: {p["accent"]};
    border-radius: 5px;
}}
QProgressBar#downloadProgressBar {{
    min-height: 10px;
    max-height: 12px;
    font-size: 8pt;
    border-radius: 4px;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea#lyricsScroll {{
    background-color: {p["bg_card"]};
    border: none;
}}
QScrollArea#lyricsScroll QLabel#lyricsLabel {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
}}
QSplitter#mainSplitter::handle:horizontal {{
    width: 4px;
    background-color: {p["bg_main"]};
}}
QSplitter#mainSplitter::handle:vertical {{
    height: 4px;
    background-color: {p["bg_main"]};
}}
QSplitter#outerSplitter::handle:horizontal {{
    width: 4px;
    background-color: {p["bg_main"]};
}}
QSplitter#outerSplitter::handle:vertical {{
    height: 4px;
    background-color: {p["bg_main"]};
}}
QWidget#lyricsWidget {{
    background-color: transparent;
}}
QMenu {{
    background-color: {p["menu_bg"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    color: {p["text_primary"]};
    padding: 8px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {p["menu_hover"]};
}}
QStatusBar {{
    background-color: {p["status_bg"]};
    border-top: 1px solid {p["border"]};
    color: {p["text_secondary"]};
    padding: 0px 6px;
    margin: 0px;
}}
QStatusBar::item {{
    border: none;
}}
QDialog {{
    background-color: {p["bg_main"]};
}}
QDialog#downloadDialog {{
    background-color: {p["bg_elevated"]};
}}
QDialog#downloadDialog QLabel {{
    color: {p["text_primary"]};
}}
QDialog#downloadDialog QPlainTextEdit,
QDialog#downloadDialog QTextEdit {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 8px;
    selection-background-color: {p["accent"]};
    selection-color: #ffffff;
}}
QDialog#downloadDialog QComboBox {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 22px;
}}
QDialog#downloadDialog QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QDialog#downloadDialog QComboBox QAbstractItemView {{
    background-color: {p["menu_bg"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    selection-background-color: {p["selection_bg"]};
    selection-color: {p["selection_fg"]};
}}
QDialog QPushButton {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    min-width: 72px;
}}
QDialog QPushButton:hover {{
    background-color: {p["menu_hover"]};
}}
QDialog QPushButton:default {{
    background-color: {p["accent"]};
    color: #ffffff;
    border-color: {p["accent"]};
}}
QPushButton#playerBtn {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    border: 1px solid {p["border"]};
    border-radius: 22px;
    padding: 0px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
}}
QPushButton#playerBtn:hover {{
    border-color: {p["accent"]};
    background-color: {p["hover_list"]};
}}
QPushButton#playerBtn:pressed {{
    background-color: {p["accent"]};
    border-color: {p["accent"]};
    color: #ffffff;
}}
QPushButton#playlistAddBtn {{
    background-color: transparent;
    color: {p["text_secondary"]};
    border: 1px solid {p["border"]};
    border-radius: 5px;
    font-size: 15px;
    font-weight: 600;
    padding: 0px 0px 1px 0px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
}}
QPushButton#playlistAddBtn:hover {{
    background-color: {p["menu_hover"]};
    color: {p["accent"]};
    border-color: {p["accent"]};
}}
QPushButton#queueToggleBtn {{
    background-color: transparent;
    color: {p["text_muted"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 4px 12px;
    font-size: 12px;
}}
QPushButton#queueToggleBtn:hover {{
    background-color: {p["menu_hover"]};
    color: {p["text_primary"]};
}}
QLabel#nowPlayingLabel {{
    color: {p["text_primary"]};
    font-size: 11pt;
    font-weight: 600;
}}
QLabel#formatLabel {{
    color: {p["text_muted"]};
    font-size: 9pt;
}}
QLabel#playlistTitle {{
    color: {p["text_primary"]};
    font-weight: 600;
    font-size: 10pt;
}}
QLabel#lyricsLabel {{
    background-color: {p["bg_card"]};
    color: {p["text_primary"]};
    font-size: 10pt;
    line-height: 1.6;
    padding: 12px;
}}
QLabel#queueHeaderLabel {{
    color: {p["text_muted"]};
    font-weight: 500;
}}
QLabel#progressTrackLabel, QLabel#pendingLabel, QLabel#volumeLabel {{
    color: {p["text_muted"]};
    font-size: 9pt;
}}
QFrame#queueListFrame {{
    background-color: {p["bg_elevated"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    margin: 0 8px 6px 8px;
}}
QListWidget#jobListWidget {{
    background-color: transparent;
    border: none;
}}
QWidget#queueHeaderRow {{
    background-color: {p["bg_main"]};
}}
QWidget#playerBottomPanel {{
    background-color: {p["bg_main"]};
}}
QWidget#playerWidget {{
    background-color: {p["bg_main"]};
}}
QFrame#progressStrip {{
    background-color: {p["bg_main"]};
    border-top: 1px solid {p["player_border"]};
}}
QVideoWidget#videoArea {{
    background-color: #000000;
    border-radius: 8px;
}}
QSlider#seekSlider::groove:horizontal,
QSlider#volSlider::groove:horizontal {{
    border: none;
    height: 5px;
    background-color: {p["border"]};
    border-radius: 2px;
    margin: 2px 0;
}}
QSlider#seekSlider::sub-page:horizontal,
QSlider#volSlider::sub-page:horizontal {{
    background-color: {p["accent"]};
    border-radius: 2px;
    height: 5px;
}}
QSlider#seekSlider::add-page:horizontal,
QSlider#volSlider::add-page:horizontal {{
    background-color: {p["border"]};
    border-radius: 2px;
    height: 5px;
}}
QSlider#seekSlider::handle:horizontal,
QSlider#volSlider::handle:horizontal {{
    background-color: {p["accent"]};
    border: 1px solid {p["bg_card"]};
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 2px;
}}
QSlider#seekSlider::handle:horizontal:hover,
QSlider#volSlider::handle:horizontal:hover {{
    background-color: {p["accent_hover"]};
}}
QScrollBar:vertical {{
    background: {p["scrollbar_track"]};
    width: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {p["scrollbar_handle"]};
    min-height: 32px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {p["scrollbar_track"]};
    height: 10px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {p["scrollbar_handle"]};
    min-width: 32px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p["scrollbar_handle_hover"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""
