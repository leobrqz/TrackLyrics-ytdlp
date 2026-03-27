"""
main.py
Application entry point.
Initialises DB, creates QApplication, shows MainWindow.
"""
import sys
from pathlib import Path

# Ensure src/ is on sys.path so all package imports resolve correctly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QStyleFactory

from core.database import init_db
from core.settings import get_setting
from ui.app_style import get_stylesheet
from ui.main_window import MainWindow


def main() -> None:
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("TrackLyrics")
    app.setOrganizationName("TrackLyrics")

    # Fusion + stylesheet palette: native Windows style ignores or fights QSS without this.
    app.setStyle(QStyleFactory.create("Fusion"))
    if hasattr(Qt.ApplicationAttribute, "AA_UseStyleSheetPalette"):
        try:
            app.setAttribute(Qt.ApplicationAttribute.AA_UseStyleSheetPalette, True)
        except (TypeError, AttributeError):
            pass

    app.setStyleSheet(get_stylesheet(get_setting("theme", "dark") or "dark"))

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
