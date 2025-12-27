"""
Dashboard widget for displaying library statistics and track listing.
"""
import logging
import traceback

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget
)

from aft.db.database import get_session_factory
from aft.db.models import Track

from ..constants import DASHBOARD_COLUMNS, TABLE_COLUMN_WIDTH_PATH

logger = logging.getLogger(__name__)


class DashboardWidget(QWidget):
    """Dashboard showing library statistics and recent activity."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("<h1>Music Library Dashboard</h1>")
        layout.addWidget(title)

        # Statistics
        self.stats_label = QLabel("Loading statistics...")
        layout.addWidget(self.stats_label)

        # Recent tracks table
        layout.addWidget(QLabel("<h3>Recent Tracks</h3>"))
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(len(DASHBOARD_COLUMNS))
        self.recent_table.setHorizontalHeaderLabels(DASHBOARD_COLUMNS)
        self.recent_table.setColumnWidth(
            len(DASHBOARD_COLUMNS) - 1, TABLE_COLUMN_WIDTH_PATH
        )  # Make path column wider
        # Enable sorting by clicking column headers
        self.recent_table.setSortingEnabled(True)
        layout.addWidget(self.recent_table)

        # Refresh button
        refresh_btn = QPushButton("Refresh Statistics")
        refresh_btn.clicked.connect(self.load_statistics)
        layout.addWidget(refresh_btn)

        self.setLayout(layout)
        self.load_statistics()

    def load_statistics(self):
        """Load library statistics from database."""
        try:
            # Show loading message
            self.stats_label.setText("Loading statistics...")
            self.recent_table.setRowCount(0)

            session_factory = get_session_factory(self.db_path)
            session = session_factory()

            total_tracks = session.query(Track).count()
            tracks_with_bpm = session.query(Track).filter(
                Track.bpm.isnot(None)).count()
            tracks_with_key = session.query(Track).filter(
                Track.key.isnot(None)).count()

            # Get recent tracks (limit to 1000 for performance)
            # User can use the Query tab to search all tracks
            # all_tracks = session.query(Track).order_by(
            #     Track.last_modified.desc()).limit(1000).all()
            all_tracks = session.query(Track).all()

            session.close()

            # Update statistics
            self.stats_label.setText(
                f"<p><b>Total Tracks:</b> {total_tracks}</p>"
                f"<p><b>Tracks with BPM:</b> {tracks_with_bpm}</p>"
                f"<p><b>Tracks with Key:</b> {tracks_with_key}</p>"
                f"<p><i>Showing most recent {len(all_tracks)} tracks</i></p>"
            )

            # Update table
            self.recent_table.setRowCount(len(all_tracks))
            for i, track in enumerate(all_tracks):
                self.recent_table.setItem(
                    i, 0, QTableWidgetItem(str(track.title or "")))
                self.recent_table.setItem(
                    i, 1, QTableWidgetItem(str(track.artist or "")))
                self.recent_table.setItem(
                    i, 2, QTableWidgetItem(str(track.album_artist or "")))
                self.recent_table.setItem(
                    i, 3, QTableWidgetItem(str(track.album or "")))
                self.recent_table.setItem(
                    i, 4, QTableWidgetItem(str(track.track_number or "")))
                self.recent_table.setItem(
                    i, 5, QTableWidgetItem(str(track.disc_number or "")))
                self.recent_table.setItem(
                    i, 6, QTableWidgetItem(str(track.year or "")))
                self.recent_table.setItem(
                    i, 7, QTableWidgetItem(str(track.genre or "")))
                self.recent_table.setItem(
                    i, 8, QTableWidgetItem(str(track.key or "")))
                bpm_str = f"{track.bpm:.1f}" if track.bpm is not None else ""
                self.recent_table.setItem(i, 9, QTableWidgetItem(bpm_str))
                duration_str = f"{track.duration:.1f}s" if track.duration is not None else ""
                self.recent_table.setItem(i, 10, QTableWidgetItem(duration_str))
                bitrate_str = f"{track.bitrate // 1000}kbps" if track.bitrate is not None else ""
                self.recent_table.setItem(i, 11, QTableWidgetItem(bitrate_str))
                sample_rate_str = f"{track.sample_rate}Hz" if track.sample_rate is not None else ""
                self.recent_table.setItem(
                    i, 12, QTableWidgetItem(sample_rate_str))
                self.recent_table.setItem(
                    i, 13, QTableWidgetItem(str(track.publisher or "")))
                self.recent_table.setItem(
                    i, 14, QTableWidgetItem(str(track.catalog_number or "")))
                self.recent_table.setItem(
                    i, 15, QTableWidgetItem(str(track.file_path or "")))

        except Exception as e:
            logger.error("Error loading statistics: %s", str(e), exc_info=True)
            self.stats_label.setText(f"Error loading statistics: {str(e)}")
            
            traceback.print_exc()
