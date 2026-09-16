"""
Query widget for searching and browsing the music library.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt

from aft.db.database import query
from aft.tags import write_audio_tags
from aft.bpm import BPM_SANITY_MIN, BPM_SANITY_MAX
from ..constants import (
    QUERY_RESULTS_COLUMNS, TABLE_COLUMN_WIDTH_PATH,
    BPM_MIN_DEFAULT, BPM_MAX_DEFAULT, BPM_RANGE_MIN, BPM_RANGE_MAX,
    SEARCH_MAX_RESULTS
)

# Column indices in QUERY_RESULTS_COLUMNS = ["Title", "Artist", "Album", "BPM", "Path"]
BPM_COLUMN = 3
PATH_COLUMN = 4

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
        self.results_table.itemChanged.connect(self.on_item_changed)
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

            # Update table. Block itemChanged while populating so the
            # BPM-edit handler doesn't fire for programmatic updates.
            self.results_table.blockSignals(True)
            try:
                self.results_table.setRowCount(len(results))
                for i, track in enumerate(results):
                    self.results_table.setItem(
                        i, 0, QTableWidgetItem(str(track.title or "")))
                    self.results_table.setItem(
                        i, 1, QTableWidgetItem(str(track.artist or "")))
                    self.results_table.setItem(
                        i, 2, QTableWidgetItem(str(track.album or "")))
                    bpm_str = f"{track.bpm:.1f}" if track.bpm is not None else ""
                    bpm_item = QTableWidgetItem(bpm_str)
                    bpm_item.setData(Qt.ItemDataRole.UserRole, bpm_str)
                    self.results_table.setItem(i, BPM_COLUMN, bpm_item)
                    self.results_table.setItem(
                        i, PATH_COLUMN, QTableWidgetItem(str(track.file_path or "")))
            finally:
                self.results_table.blockSignals(False)

        except Exception as e:
            logger.error("Error executing query: %s", str(e))
            QMessageBox.critical(self, "Query Error",
                                 f"Error executing query:\n{str(e)}")

    def on_item_changed(self, item: QTableWidgetItem):
        """Handle manual edits to the results table (currently: BPM only).

        Writes straight to the file's tag via the centralized write path, so
        a later rescan/re-ingest picks up the corrected value. The library
        DB row is not updated here - it's a rescan-derived cache per the
        existing scan_library/incremental_update architecture, and will
        reflect the edit on the next scan.
        """
        if item.column() != BPM_COLUMN:
            return

        row = item.row()
        path_item = self.results_table.item(row, PATH_COLUMN)
        if path_item is None or not path_item.text():
            return
        file_path = path_item.text()

        new_text = item.text().strip()
        original_text = item.data(Qt.ItemDataRole.UserRole)

        def revert():
            self.results_table.blockSignals(True)
            try:
                item.setText(original_text or "")
            finally:
                self.results_table.blockSignals(False)

        try:
            new_bpm = float(new_text) if new_text else None
        except ValueError:
            QMessageBox.warning(self, "Invalid BPM", f"'{new_text}' is not a valid BPM value.")
            revert()
            return

        if new_bpm is not None and not (BPM_SANITY_MIN <= new_bpm <= BPM_SANITY_MAX):
            QMessageBox.warning(
                self, "Invalid BPM",
                f"BPM must be between {BPM_SANITY_MIN:.0f} and {BPM_SANITY_MAX:.0f}."
            )
            revert()
            return

        if new_bpm is None:
            return

        success = write_audio_tags(file_path, {'bpm': new_bpm})
        if not success:
            QMessageBox.warning(self, "Write Failed", f"Could not write BPM to:\n{file_path}")
            revert()
            return

        self.results_table.blockSignals(True)
        try:
            item.setText(f"{new_bpm:.1f}")
            item.setData(Qt.ItemDataRole.UserRole, item.text())
        finally:
            self.results_table.blockSignals(False)
