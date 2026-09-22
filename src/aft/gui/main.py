"""
Main GUI application for audio files tagging.

Desktop application built with PySide6 (Qt for Python).

Usage:
    python -m aft.gui.main --db "data/library.db"
"""
import sys
import logging
import argparse

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QMessageBox
from PySide6.QtGui import QAction

from aft.db.database import init_db
from .widgets import DashboardWidget, DiscogsLookupWidget, QueryWidget, IngestWidget
from .constants import (
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_X, WINDOW_Y,
    DEFAULT_DB_PATH, APP_STYLE, LOG_FORMAT, LOG_LEVEL, STATUS_READY
)
from .styles import MAIN_STYLESHEET

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        super().__init__()
        self.db_path = db_path
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(WINDOW_X, WINDOW_Y, WINDOW_WIDTH, WINDOW_HEIGHT)

        # Create menu bar
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        init_db_action = QAction("&Initialize Database", self)
        init_db_action.triggered.connect(self.init_database)
        file_menu.addAction(init_db_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Create tab widget
        tabs = QTabWidget()

        # Add tabs
        tabs.addTab(DashboardWidget(self.db_path, self), "Dashboard")
        tabs.addTab(DiscogsLookupWidget(self.db_path, self), "Metadata Tools")
        tabs.addTab(QueryWidget(self.db_path, self), "Query Library")
        tabs.addTab(IngestWidget(self.db_path, self), "Batch Ingest")

        self.setCentralWidget(tabs)

        # Apply stylesheet
        self.setStyleSheet(MAIN_STYLESHEET)

        # Status bar
        self.statusBar().showMessage(STATUS_READY)

    def init_database(self):
        """Initialize database."""
        try:
            init_db(self.db_path)
            QMessageBox.information(
                self,
                "Database Initialized",
                f"Database initialized successfully at:\n{self.db_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Database Error",
                f"Error initializing database:\n{str(e)}"
            )


def main(db_path: str = DEFAULT_DB_PATH):
    """
    Run the GUI application.

    Parameters
    ----------
    db_path : str
        Path to SQLite database file
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT
    )

    app = QApplication(sys.argv)
    app.setStyle(APP_STYLE)

    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audio Files Tagging GUI")
    parser.add_argument(
        "--db",
        default="data/library.db",
        help="Path to SQLite database file"
    )

    args = parser.parse_args()
    main(args.db)
