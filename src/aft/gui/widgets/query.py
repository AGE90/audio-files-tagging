"""
Query widget for searching and browsing the music library.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox
)

from aft.db.database import query
from ..constants import (
    QUERY_RESULTS_COLUMNS, TABLE_COLUMN_WIDTH_PATH,
    BPM_MIN_DEFAULT, BPM_MAX_DEFAULT, BPM_RANGE_MIN, BPM_RANGE_MAX,
    SEARCH_MAX_RESULTS
)

logger = logging.getLogger(__name__)


class QueryWidget(QWidget):
    """Widget for querying and browsing the music library."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("<h2>Query Library</h2>")
        layout.addWidget(title)

        # Search form
        form_layout = QVBoxLayout()

        # Artist filter
        artist_layout = QHBoxLayout()
        artist_layout.addWidget(QLabel("Artist:"))
        self.artist_input = QLineEdit()
        artist_layout.addWidget(self.artist_input)
        form_layout.addLayout(artist_layout)

        # Album filter
        album_layout = QHBoxLayout()
        album_layout.addWidget(QLabel("Album:"))
        self.album_input = QLineEdit()
        album_layout.addWidget(self.album_input)
        form_layout.addLayout(album_layout)

        # BPM range
        bpm_layout = QHBoxLayout()
        bpm_layout.addWidget(QLabel("BPM Range:"))
        self.bpm_min_input = QSpinBox()
        self.bpm_min_input.setRange(BPM_RANGE_MIN, BPM_RANGE_MAX)
        self.bpm_min_input.setValue(BPM_MIN_DEFAULT)
        bpm_layout.addWidget(self.bpm_min_input)
        bpm_layout.addWidget(QLabel("-"))
        self.bpm_max_input = QSpinBox()
        self.bpm_max_input.setRange(BPM_RANGE_MIN, BPM_RANGE_MAX)
        self.bpm_max_input.setValue(BPM_MAX_DEFAULT)
        bpm_layout.addWidget(self.bpm_max_input)
        form_layout.addLayout(bpm_layout)

        # Search button
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.search)
        form_layout.addWidget(search_btn)

        layout.addLayout(form_layout)

        # Results table
        layout.addWidget(QLabel("<h3>Results</h3>"))
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(QUERY_RESULTS_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(QUERY_RESULTS_COLUMNS)
        self.results_table.setColumnWidth(
            len(QUERY_RESULTS_COLUMNS) - 1, TABLE_COLUMN_WIDTH_PATH
        )
        layout.addWidget(self.results_table)

        self.setLayout(layout)

    def search(self):
        """Execute search."""
        try:
            artist = self.artist_input.text() or None
            album = self.album_input.text() or None

            bpm_min = self.bpm_min_input.value()
            bpm_max = self.bpm_max_input.value()
            bpm_range = (bpm_min, bpm_max) if bpm_min < bpm_max else None

            # Query database
            results = query(
                artist=artist,
                album=album,
                bpm_range=bpm_range,
                limit=SEARCH_MAX_RESULTS,
                db_path=self.db_path
            )

            # Update table
            self.results_table.setRowCount(len(results))
            for i, track in enumerate(results):
                self.results_table.setItem(
                    i, 0, QTableWidgetItem(str(track.title or "")))
                self.results_table.setItem(
                    i, 1, QTableWidgetItem(str(track.artist or "")))
                self.results_table.setItem(
                    i, 2, QTableWidgetItem(str(track.album or "")))
                bpm_str = f"{track.bpm:.1f}" if track.bpm is not None else ""
                self.results_table.setItem(i, 3, QTableWidgetItem(bpm_str))
                self.results_table.setItem(
                    i, 4, QTableWidgetItem(str(track.file_path or "")))

        except Exception as e:
            logger.error("Error executing query: %s", str(e))
            QMessageBox.critical(self, "Query Error",
                                 f"Error executing query:\n{str(e)}")
