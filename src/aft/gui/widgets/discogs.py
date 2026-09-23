"""
Discogs lookup widget for fetching and applying metadata from Discogs API.
"""
import logging
import os
from difflib import SequenceMatcher
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QAbstractItemView, QCheckBox,
    QGroupBox, QFormLayout, QSpinBox, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal

from aft.discogs_client import DiscogsClient
from aft.tags import read_audio_tags, write_audio_tags, embed_cover_art
from aft.bpm import analyze_and_tag_bpm
from aft.key import analyze_and_tag_key
from aft.ingest import normalize_filename
from aft.db.database import update_track_path
from aft import credentials
from ..constants import (
    DISCOGS_RESULTS_COLUMNS, DISCOGS_MAX_RESULTS,
    AUDIO_FILE_FILTER, STATUS_DISCOGS_CONNECTED,
    STATUS_DISCOGS_NO_TOKEN, STATUS_DISCOGS_ERROR,
    TABLE_COLUMN_WIDTH_PATH
)

# Track metadata table columns
TRACK_METADATA_COLUMNS = [
    "Track #", "Title", "Composer", "Artist", "Album", "Year",
    "Genre", "Duration", "File Path"
]

# Discogs tracklist table columns
DISCOGS_TRACKLIST_COLUMNS = [
    "Position", "Title", "Duration", "Matched File"
]

logger = logging.getLogger(__name__)


class ApplyMetadataWorker(QThread):
    """Worker thread for writing metadata (and optionally BPM/key) to files."""

    finished = Signal(int, list)  # success_count, errors

    def __init__(
        self,
        file_metadata: list[tuple[str, dict]],
        analyze_bpm: bool,
        analyze_key: bool = False,
        dry_run: bool = False,
    ):
        super().__init__()
        self.file_metadata = file_metadata
        self.analyze_bpm = analyze_bpm
        self.analyze_key = analyze_key
        self.dry_run = dry_run

    def run(self):
        success_count = 0
        errors = []

        for file_path, metadata_to_write in self.file_metadata:
            try:
                if self.analyze_bpm:
                    existing_bpm = read_audio_tags(file_path).get('bpm')
                    if not existing_bpm:
                        # Still detect BPM in a dry run for preview purposes,
                        # just don't persist it
                        bpm_result = analyze_and_tag_bpm(
                            file_path, write_tag=not self.dry_run)
                        logger.info(
                            "BPM analysis for %s: %s", file_path, bpm_result.get('bpm'))

                if self.analyze_key:
                    existing_key = read_audio_tags(file_path).get('key')
                    if not existing_key:
                        key_result = analyze_and_tag_key(
                            file_path, write_tag=not self.dry_run)
                        logger.info(
                            "Key analysis for %s: %s", file_path, key_result.get('key'))

                if self.dry_run:
                    logger.info(
                        "[DRY RUN] Would write to %s: %s", file_path, metadata_to_write)
                    success = True
                else:
                    success = write_audio_tags(file_path, metadata_to_write)

                if success:
                    success_count += 1
                else:
                    errors.append(f"{file_path}: Failed to write")
            except Exception as e:
                logger.error("Error applying metadata to %s: %s", file_path, str(e))
                errors.append(f"{file_path}: {str(e)}")

        self.finished.emit(success_count, errors)


class DiscogsLookupWidget(QWidget):
    """Widget for looking up and applying metadata from Discogs."""

    send_to_ingest = Signal(str)  # Common folder of the currently loaded tracks

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.discogs_client = None
        # Store list of loaded tracks with their metadata
        # Each item: {"file_path": str, "metadata": dict, "discogs_match": dict}
        self.loaded_tracks: list[dict] = []
        self.selected_release_data = None
        self.apply_worker = None
        self._last_apply_was_dry_run = False
        self.init_ui()
        self.init_discogs_client()

    def init_discogs_client(self):
        """Initialize Discogs client with user token."""
        try:
            if credentials.discogs_user_token:
                self.discogs_client = DiscogsClient(
                    user_token=credentials.discogs_user_token
                )
                self.status_label.setText(STATUS_DISCOGS_CONNECTED)
            else:
                self.status_label.setText(STATUS_DISCOGS_NO_TOKEN)
        except Exception as e:
            logger.error("Error initializing Discogs client: %s", str(e))
            self.status_label.setText(STATUS_DISCOGS_ERROR.format(e))

    def init_ui(self):
        """Initialize UI."""
        # Create a scroll area for the entire widget
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create container widget for scroll area
        container = QWidget()
        layout = QVBoxLayout(container)

        # Title
        title = QLabel("<h2>Metadata Tools</h2>")
        layout.addWidget(title)

        # Status label
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)

        # Main horizontal split: file/tracks on the left, Discogs tools on
        # the right. Both sides are splitters so the user can resize panels
        # instead of fighting fixed pixel heights.
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # === LEFT PANEL: File Management ===
        left_panel = QWidget()
        left_column = QVBoxLayout(left_panel)

        # File selection section
        file_section = QHBoxLayout()
        file_section.addWidget(QLabel("<b>Audio Files:</b>"))
        self.file_count_label = QLabel("No files loaded")
        file_section.addWidget(self.file_count_label, 1)
        browse_btn = QPushButton("Load Files...")
        browse_btn.clicked.connect(self.browse_files)
        file_section.addWidget(browse_btn)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_files)
        file_section.addWidget(clear_btn)
        self.send_to_ingest_btn = QPushButton("Send to Batch Ingest")
        self.send_to_ingest_btn.setEnabled(False)
        self.send_to_ingest_btn.clicked.connect(self.send_release_to_ingest)
        file_section.addWidget(self.send_to_ingest_btn)
        left_column.addLayout(file_section)

        # Current tracks metadata table
        left_column.addWidget(QLabel("<h3>Loaded Tracks</h3>"))
        self.tracks_table = QTableWidget()
        self.tracks_table.setColumnCount(len(TRACK_METADATA_COLUMNS))
        self.tracks_table.setHorizontalHeaderLabels(TRACK_METADATA_COLUMNS)
        self.tracks_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tracks_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        # Make Track # and Title columns editable
        self.tracks_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.tracks_table.itemChanged.connect(self.on_track_item_changed)
        self.tracks_table.setColumnWidth(
            len(TRACK_METADATA_COLUMNS) - 1, TABLE_COLUMN_WIDTH_PATH)
        self.tracks_table.setMinimumHeight(200)
        # Take all available vertical space in the panel
        left_column.addWidget(self.tracks_table, 1)

        main_splitter.addWidget(left_panel)

        # === RIGHT PANEL: Discogs search, matching and apply ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Search Discogs - compact, pinned at the top
        search_group = QGroupBox("Search Discogs")
        search_group_layout = QVBoxLayout()

        artist_search_layout = QHBoxLayout()
        artist_search_layout.addWidget(QLabel("Artist:"))
        self.artist_search_input = QLineEdit()
        artist_search_layout.addWidget(self.artist_search_input)
        search_group_layout.addLayout(artist_search_layout)

        release_search_layout = QHBoxLayout()
        release_search_layout.addWidget(QLabel("Release:"))
        self.release_search_input = QLineEdit()
        release_search_layout.addWidget(self.release_search_input)
        search_group_layout.addLayout(release_search_layout)

        search_btn = QPushButton("Search Discogs")
        search_btn.clicked.connect(self.search_discogs)
        search_group_layout.addWidget(search_btn)

        search_group.setLayout(search_group_layout)
        right_layout.addWidget(search_group)

        # Resizable middle section: results/details, metadata form, tracklist
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Search results + selected release details
        results_group = QGroupBox("Search Results and Release Details")
        results_group_layout = QVBoxLayout()
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(len(DISCOGS_RESULTS_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(DISCOGS_RESULTS_COLUMNS)
        self.results_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection)
        self.results_table.itemSelectionChanged.connect(
            self.on_release_selected)
        self.results_table.setMinimumHeight(100)
        results_group_layout.addWidget(self.results_table, 1)

        self.release_details_text = QTextEdit()
        self.release_details_text.setReadOnly(True)
        self.release_details_text.setMinimumHeight(60)
        self.release_details_text.setMaximumHeight(120)
        results_group_layout.addWidget(self.release_details_text)

        results_group.setLayout(results_group_layout)
        right_splitter.addWidget(results_group)

        # Editable release-level metadata
        release_metadata_group = QGroupBox(
            "Release Metadata (Edit before applying)")
        release_metadata_layout = QFormLayout()

        self.album_input = QLineEdit()
        release_metadata_layout.addRow("Album:", self.album_input)

        self.album_artist_input = QLineEdit()
        release_metadata_layout.addRow(
            "Album Artist:", self.album_artist_input)

        self.year_input = QSpinBox()
        self.year_input.setRange(0, 9999)
        self.year_input.setSpecialValueText("Unknown")
        release_metadata_layout.addRow("Year:", self.year_input)

        self.genre_input = QLineEdit()
        release_metadata_layout.addRow("Genre:", self.genre_input)

        self.label_input = QLineEdit()
        release_metadata_layout.addRow("Label:", self.label_input)

        self.catalog_number_input = QLineEdit()
        release_metadata_layout.addRow("Catalog #:", self.catalog_number_input)

        release_metadata_group.setLayout(release_metadata_layout)
        right_splitter.addWidget(release_metadata_group)

        # Discogs tracklist display
        tracklist_group = QGroupBox("Discogs Tracklist (Auto-matched to loaded files)")
        tracklist_group_layout = QVBoxLayout()
        self.tracklist_table = QTableWidget()
        self.tracklist_table.setColumnCount(len(DISCOGS_TRACKLIST_COLUMNS))
        self.tracklist_table.setHorizontalHeaderLabels(
            DISCOGS_TRACKLIST_COLUMNS)
        self.tracklist_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tracklist_table.setMinimumHeight(80)
        tracklist_group_layout.addWidget(self.tracklist_table)
        tracklist_group.setLayout(tracklist_group_layout)
        right_splitter.addWidget(tracklist_group)

        # Additional tools: cover art embedding and filename normalization,
        # both operating on the currently loaded tracks. This is the home
        # for future tagging tools beyond Discogs lookup.
        tools_group = QGroupBox("Additional Tools")
        tools_group_layout = QVBoxLayout()

        cover_art_layout = QHBoxLayout()
        cover_art_layout.addWidget(QLabel("Cover Art:"))
        self.cover_art_input = QLineEdit()
        cover_art_layout.addWidget(self.cover_art_input)
        cover_art_browse_btn = QPushButton("Browse...")
        cover_art_browse_btn.clicked.connect(self.browse_cover_art)
        cover_art_layout.addWidget(cover_art_browse_btn)
        self.embed_cover_art_btn = QPushButton("Embed in Loaded Tracks")
        self.embed_cover_art_btn.clicked.connect(self.embed_cover_art_to_tracks)
        cover_art_layout.addWidget(self.embed_cover_art_btn)
        tools_group_layout.addLayout(cover_art_layout)

        filename_layout = QHBoxLayout()
        self.fix_filenames_btn = QPushButton("Fix Filenames in Loaded Tracks")
        self.fix_filenames_btn.clicked.connect(self.fix_filenames)
        filename_layout.addWidget(self.fix_filenames_btn)
        self.tools_status_label = QLabel("")
        filename_layout.addWidget(self.tools_status_label, 1)
        tools_group_layout.addLayout(filename_layout)

        tools_group.setLayout(tools_group_layout)
        right_splitter.addWidget(tools_group)

        # Results and tracklist (the two tables) get most of the resizable
        # space; the metadata form and tools panel only need their natural
        # height
        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 0)
        right_splitter.setStretchFactor(2, 2)
        right_splitter.setStretchFactor(3, 0)

        right_layout.addWidget(right_splitter, 1)

        # Apply metadata section - pinned action bar at the bottom
        apply_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Metadata to File")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.apply_metadata)
        apply_layout.addWidget(self.apply_btn)

        self.analyze_bpm_checkbox = QCheckBox("Also compute BPM")
        self.analyze_bpm_checkbox.setChecked(True)
        apply_layout.addWidget(self.analyze_bpm_checkbox)

        self.analyze_key_checkbox = QCheckBox("Also compute Key")
        self.analyze_key_checkbox.setChecked(True)
        apply_layout.addWidget(self.analyze_key_checkbox)

        self.dry_run_checkbox = QCheckBox("Dry Run (preview only)")
        apply_layout.addWidget(self.dry_run_checkbox)

        self.apply_status_label = QLabel("")
        apply_layout.addWidget(self.apply_status_label, 1)
        right_layout.addLayout(apply_layout)

        main_splitter.addWidget(right_panel)
        # Right panel starts wider since it stacks more sections
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([450, 750])

        layout.addWidget(main_splitter, 1)

        # Set the container in the scroll area
        scroll.setWidget(container)
        
        # Set scroll area as main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def browse_files(self):
        """Browse for audio files (supports multiple selection)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Audio Files",
            "",
            AUDIO_FILE_FILTER
        )
        if file_paths:
            self.load_files(file_paths)

    def clear_files(self):
        """Clear all loaded tracks."""
        self.loaded_tracks.clear()
        self.tracks_table.setRowCount(0)
        self.file_count_label.setText("No files loaded")
        self.apply_btn.setEnabled(False)
        self.send_to_ingest_btn.setEnabled(False)
        self.tracklist_table.setRowCount(0)

    def send_release_to_ingest(self):
        """Emit the loaded tracks' common folder for the Batch Ingest tab.

        Lets the Batch Ingest tab pick up right where metadata editing left
        off, without re-browsing for a folder the user just worked in.
        """
        if not self.loaded_tracks:
            return

        parent_dirs = {str(Path(t["file_path"]).parent) for t in self.loaded_tracks}
        common_dir = os.path.commonpath(list(parent_dirs))
        self.send_to_ingest.emit(common_dir)

    def browse_cover_art(self):
        """Browse for a cover art image."""
        image_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cover Art", "",
            "Images (*.jpg *.jpeg *.png)"
        )
        if image_path:
            self.cover_art_input.setText(image_path)

    def embed_cover_art_to_tracks(self):
        """Embed the selected cover art image into every loaded track."""
        if not self.loaded_tracks:
            return

        image_path = self.cover_art_input.text().strip()
        if not image_path:
            QMessageBox.warning(self, "No Image", "Please select a cover art image first.")
            return

        if not Path(image_path).exists():
            QMessageBox.warning(self, "Image Not Found", f"File does not exist:\n{image_path}")
            return

        success_count = 0
        errors = []
        for track_info in self.loaded_tracks:
            file_path = track_info["file_path"]
            try:
                if embed_cover_art(file_path, image_path):
                    success_count += 1
                else:
                    errors.append(file_path)
            except Exception as e:
                logger.error("Error embedding cover art in %s: %s", file_path, str(e))
                errors.append(file_path)

        if errors:
            self.tools_status_label.setText(
                f"⚠ Embedded cover art in {success_count}/{len(self.loaded_tracks)} file(s)")
            QMessageBox.warning(
                self, "Partial Success",
                f"Embedded in {success_count}/{len(self.loaded_tracks)} file(s).\n\n"
                "Failed:\n" + "\n".join(errors[:5]) +
                (f"\n...and {len(errors) - 5} more" if len(errors) > 5 else "")
            )
        else:
            self.tools_status_label.setText(
                f"✓ Embedded cover art in {success_count} file(s)")

    def fix_filenames(self):
        """
        Rename each loaded track's file to its normalized form (illegal
        characters and trailing dots/spaces stripped - the same rule the
        ingest pipeline applies to new files), keeping the DB in sync.
        """
        if not self.loaded_tracks:
            return

        renamed_count = 0
        errors = []
        for track_info in self.loaded_tracks:
            old_path = Path(track_info["file_path"])
            new_name = normalize_filename(old_path.name)
            if new_name == old_path.name:
                continue

            new_path = old_path.parent / new_name
            if new_path.exists():
                errors.append(f"{old_path.name}: target already exists")
                continue

            try:
                old_path.rename(new_path)
                update_track_path(str(old_path), str(new_path), db_path=self.db_path)
                track_info["file_path"] = str(new_path)
                renamed_count += 1
            except OSError as e:
                logger.error("Error renaming %s: %s", old_path, str(e))
                errors.append(f"{old_path.name}: {str(e)}")

        self.refresh_tracks_table()

        if errors:
            self.tools_status_label.setText(
                f"⚠ Renamed {renamed_count} file(s), {len(errors)} error(s)")
            QMessageBox.warning(
                self, "Partial Success",
                f"Renamed {renamed_count} file(s).\n\nErrors:\n" + "\n".join(errors[:5]) +
                (f"\n...and {len(errors) - 5} more" if len(errors) > 5 else "")
            )
        elif renamed_count:
            self.tools_status_label.setText(f"✓ Renamed {renamed_count} file(s)")
        else:
            self.tools_status_label.setText("No filenames needed fixing")

    def load_files(self, file_paths: list[str]):
        """Load multiple audio files and display their metadata."""
        errors = []

        for file_path in file_paths:
            try:
                # Read current metadata
                metadata = read_audio_tags(file_path)

                # Store track info
                track_info = {
                    "file_path": file_path,
                    "metadata": metadata,
                    "discogs_match": None,  # Will be populated when matching
                    "edited_track_number": metadata.get('track_number'),
                    "edited_title": metadata.get('title'),
                    "edited_composer": metadata.get('composer'),
                }
                self.loaded_tracks.append(track_info)

            except Exception as e:
                logger.error("Error loading file %s: %s", file_path, str(e))
                errors.append(f"{file_path}: {str(e)}")

        # Update UI
        self.refresh_tracks_table()
        self.file_count_label.setText(
            f"{len(self.loaded_tracks)} file(s) loaded")

        # Auto-fill search fields and the editable release-metadata form
        # from the first track's existing tags, so manual edits (without
        # ever selecting a Discogs release) start from real values
        if self.loaded_tracks:
            first_metadata = self.loaded_tracks[0]["metadata"]
            artist = first_metadata.get('artist', '')
            album = first_metadata.get('album', '')
            if artist:
                self.artist_search_input.setText(artist)
            if album:
                self.release_search_input.setText(album)

            self.album_input.setText(album)
            self.album_artist_input.setText(first_metadata.get('album_artist', ''))
            try:
                self.year_input.setValue(int(first_metadata.get('year') or 0))
            except (TypeError, ValueError):
                self.year_input.setValue(0)
            self.genre_input.setText(first_metadata.get('genre', ''))
            self.label_input.setText(first_metadata.get('publisher', ''))
            self.catalog_number_input.setText(first_metadata.get('catalog_number', ''))

        # Apply is usable as soon as files are loaded - a Discogs match is
        # optional, not required, for manual metadata editing
        self.apply_btn.setEnabled(len(self.loaded_tracks) > 0)
        self.send_to_ingest_btn.setEnabled(len(self.loaded_tracks) > 0)

        # Show errors if any
        if errors:
            QMessageBox.warning(
                self, "Loading Errors",
                "Could not load some files:\n\n" + "\n".join(errors[:5]) +
                (f"\n\n...and {len(errors) - 5} more" if len(errors) > 5 else "")
            )

    def refresh_tracks_table(self):
        """Refresh the tracks table with current loaded tracks."""
        self.tracks_table.blockSignals(
            True)  # Prevent itemChanged signals during refresh
        self.tracks_table.setRowCount(len(self.loaded_tracks))

        for i, track_info in enumerate(self.loaded_tracks):
            metadata = track_info["metadata"]

            # Track # (editable)
            track_num = track_info.get(
                "edited_track_number") or metadata.get('track_number', '')
            track_num_item = QTableWidgetItem(
                str(track_num) if track_num else "")
            self.tracks_table.setItem(i, 0, track_num_item)

            # Title (editable)
            title = track_info.get("edited_title") or metadata.get('title', '')
            title_item = QTableWidgetItem(str(title) if title else "")
            self.tracks_table.setItem(i, 1, title_item)

            # Composer (editable)
            composer = track_info.get(
                "edited_composer") or metadata.get('composer', '')
            composer_item = QTableWidgetItem(str(composer) if composer else "")
            self.tracks_table.setItem(i, 2, composer_item)

            # Artist (read-only)
            artist_item = QTableWidgetItem(str(metadata.get('artist', '')))
            artist_item.setFlags(artist_item.flags() & ~
                                 Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 3, artist_item)

            # Album (read-only)
            album_item = QTableWidgetItem(str(metadata.get('album', '')))
            album_item.setFlags(album_item.flags() & ~
                                Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 4, album_item)

            # Year (read-only)
            year_item = QTableWidgetItem(str(metadata.get('year', '')))
            year_item.setFlags(year_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 5, year_item)

            # Genre (read-only)
            genre = metadata.get('genre', '')
            if isinstance(genre, list):
                genre = ', '.join(genre)
            genre_item = QTableWidgetItem(str(genre))
            genre_item.setFlags(genre_item.flags() & ~
                                Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 6, genre_item)

            # Duration (read-only)
            duration = metadata.get('duration')
            duration_str = f"{duration:.1f}s" if duration else ""
            duration_item = QTableWidgetItem(duration_str)
            duration_item.setFlags(duration_item.flags()
                                   & ~Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 7, duration_item)

            # File Path (read-only)
            path_item = QTableWidgetItem(track_info["file_path"])
            path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tracks_table.setItem(i, 8, path_item)

        self.tracks_table.blockSignals(False)

    def on_track_item_changed(self, item: QTableWidgetItem):
        """Handle manual edits to track table (track number, title, composer)."""
        row = item.row()
        col = item.column()

        if row >= len(self.loaded_tracks):
            return

        track_info = self.loaded_tracks[row]

        # Only handle Track # (col 0), Title (col 1), and Composer (col 2)
        if col == 0:  # Track #
            track_info["edited_track_number"] = item.text()
        elif col == 1:  # Title
            track_info["edited_title"] = item.text()
        elif col == 2:  # Composer
            track_info["edited_composer"] = item.text()

    def search_discogs(self):
        """Search Discogs for releases."""
        if not self.discogs_client:
            QMessageBox.warning(
                self, "No API Connection", "Discogs API client not initialized")
            return

        artist = self.artist_search_input.text().strip()
        release = self.release_search_input.text().strip()

        if not release:
            QMessageBox.warning(
                self, "Missing Information", "Please enter a release title to search")
            return

        try:
            # Search for releases
            results = self.discogs_client.search_release(
                release_title=release,
                artist=artist if artist else None,
                max_results=DISCOGS_MAX_RESULTS
            )

            # Display results
            self.results_table.setRowCount(len(results))
            for i, release_data in enumerate(results):
                self.results_table.setItem(
                    i, 0, QTableWidgetItem(str(release_data['id'])))
                self.results_table.setItem(
                    i, 1, QTableWidgetItem(release_data['title']))
                artists = ', '.join(release_data.get('artist', []))
                self.results_table.setItem(i, 2, QTableWidgetItem(artists))
                self.results_table.setItem(
                    i, 3, QTableWidgetItem(str(release_data.get('year', ''))))
                formats = ', '.join(release_data.get('format', []))
                self.results_table.setItem(i, 4, QTableWidgetItem(formats))

            if results:
                self.apply_status_label.setText(
                    f"Found {len(results)} results")
            else:
                self.apply_status_label.setText("No results found")

        except Exception as e:
            logger.error("Error searching Discogs: %s", str(e))
            QMessageBox.critical(
                self, "Search Error", f"Error searching Discogs:\n{str(e)}")

    def on_release_selected(self):
        """Handle release selection from results table."""
        selected_rows = self.results_table.selectedIndexes()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        release_id = int(self.results_table.item(row, 0).text())

        try:
            # Get full release details
            self.selected_release_data = self.discogs_client.get_release_by_id(
                release_id)

            if self.selected_release_data:
                # Display release details
                details = self._format_release_details(
                    self.selected_release_data)
                self.release_details_text.setPlainText(details)

                # Populate editable release metadata fields
                release = self.selected_release_data
                self.album_input.setText(release.get('title', ''))

                artists = release.get('artist', [])
                self.album_artist_input.setText(artists[0] if artists else '')

                self.year_input.setValue(
                    int(release.get('year', 0)) if release.get('year') else 0)

                # Combine genres and styles separated by semicolons
                genres = release.get('genres', [])
                styles = release.get('styles', [])
                combined_genres = genres + styles
                self.genre_input.setText('; '.join(combined_genres) if combined_genres else '')

                labels = release.get('labels', [])
                self.label_input.setText(', '.join(labels) if labels else '')

                catalog_numbers = release.get('catalog_numbers', [])
                self.catalog_number_input.setText(
                    ', '.join(catalog_numbers) if catalog_numbers else '')

                # Match Discogs tracklist to loaded files
                self.match_tracklist_to_files()

                # Enable apply button if we have tracks loaded
                self.apply_btn.setEnabled(len(self.loaded_tracks) > 0)
            else:
                self.release_details_text.setPlainText(
                    "Could not load release details")

        except Exception as e:
            logger.error("Error loading release details: %s", str(e))
            QMessageBox.critical(
                self, "Error", f"Error loading release details:\n{str(e)}")

    def match_tracklist_to_files(self):
        """Match Discogs tracklist to loaded audio files."""
        if not self.selected_release_data or not self.loaded_tracks:
            self.tracklist_table.setRowCount(0)
            return

        tracklist = self.selected_release_data.get('tracklist', [])
        if not tracklist:
            self.tracklist_table.setRowCount(0)
            return

        # Create a working copy of tracks for matching
        unmatched_tracks = list(self.loaded_tracks)

        # Display tracklist and attempt matching
        self.tracklist_table.setRowCount(len(tracklist))

        for i, discogs_track in enumerate(tracklist):
            position = discogs_track.get('position', '')
            title = discogs_track.get('title', '')
            duration = discogs_track.get('duration', '')

            # Try to match this Discogs track to a loaded file
            matched_file = self._find_matching_track(
                discogs_track, unmatched_tracks
            )

            # Populate table row
            self.tracklist_table.setItem(i, 0, QTableWidgetItem(position))
            self.tracklist_table.setItem(i, 1, QTableWidgetItem(title))
            self.tracklist_table.setItem(i, 2, QTableWidgetItem(duration))

            if matched_file:
                matched_path = matched_file["file_path"].split(
                    "\\")[-1]  # Show filename only
                self.tracklist_table.setItem(
                    i, 3, QTableWidgetItem(f"✓ {matched_path}"))

                # Store match in track info
                matched_file["discogs_match"] = discogs_track

                # Update edited track number and title from Discogs
                matched_file["edited_track_number"] = position
                matched_file["edited_title"] = title

                # Discogs doesn't always credit a composer - don't clobber
                # whatever was already loaded (file tag or manual edit)
                # with a blank when it has none for this track
                composer = discogs_track.get('composer', '')
                if composer:
                    matched_file["edited_composer"] = composer

                # Remove from unmatched list
                unmatched_tracks.remove(matched_file)
            else:
                self.tracklist_table.setItem(
                    i, 3, QTableWidgetItem("✗ No match"))

        # Refresh tracks table to show updated track numbers and titles
        self.refresh_tracks_table()

    def _find_matching_track(self, discogs_track: dict, available_tracks: list[dict]) -> dict | None:
        """Find the best matching local track for a Discogs track."""
        if not available_tracks:
            return None

        discogs_position = discogs_track.get('position', '')
        discogs_title = discogs_track.get('title', '').lower()

        # Extract numeric track number from position (e.g., "A1" -> 1, "1" -> 1)
        try:
            # Remove non-numeric characters and parse
            discogs_track_num = int(
                ''.join(filter(str.isdigit, discogs_position)))
        except (ValueError, TypeError):
            discogs_track_num = None

        # Strategy 1: Match by track number (most reliable)
        if discogs_track_num is not None:
            for track in available_tracks:
                file_track_num = track["metadata"].get('track_number')
                if file_track_num == discogs_track_num:
                    return track

        # Strategy 2: Match by title similarity (fallback)
        if discogs_title:
            best_match = None
            best_ratio = 0.0

            for track in available_tracks:
                file_title = track["metadata"].get('title', '').lower()
                if file_title:
                    ratio = SequenceMatcher(
                        None, discogs_title, file_title).ratio()
                    if ratio > best_ratio and ratio > 0.6:  # 60% similarity threshold
                        best_ratio = ratio
                        best_match = track

            if best_match:
                return best_match

        # No good match found
        return None

    def _format_release_details(self, release_data: dict) -> str:
        """Format release data for display."""
        details = "Discogs metadata:\n\n"
        details += f"Title: {release_data.get('title', 'N/A')}\n"
        details += f"Artist: {', '.join(release_data.get('artist', []))}\n"
        details += f"Year: {release_data.get('year', 'N/A')}\n"
        details += f"Genres: {', '.join(release_data.get('genres', []))}\n"
        details += f"Styles: {', '.join(release_data.get('styles', []))}\n"
        details += f"Labels: {', '.join(release_data.get('labels', []))}\n"
        details += f"Catalog #: {', '.join(release_data.get('catalog_numbers', []))}\n"
        details += f"Country: {release_data.get('country', 'N/A')}\n"
        details += f"Format: {', '.join(release_data.get('format', []))}\n"

        if release_data.get('tracklist'):
            details += "\nTracklist:\n"
            for track in release_data['tracklist']:
                details += f"  {track['position']}. {track['title']}"
                if track.get('duration'):
                    details += f" ({track['duration']})"
                details += "\n"

        if release_data.get('notes'):
            details += f"\nNotes: {release_data['notes']}\n"

        return details

    def apply_metadata(self):
        """Apply metadata to all loaded audio files.

        Works with or without a selected Discogs release - the release
        metadata fields can be filled in by hand for releases that aren't
        on Discogs at all.
        """
        if not self.loaded_tracks:
            return

        # Collect release-level metadata from editable fields
        release_metadata = {}

        if self.album_input.text().strip():
            release_metadata['album'] = self.album_input.text().strip()

        if self.album_artist_input.text().strip():
            release_metadata['album_artist'] = self.album_artist_input.text(
            ).strip()

        if self.year_input.value() > 0:
            release_metadata['year'] = self.year_input.value()

        if self.genre_input.text().strip():
            # Split semicolon-separated genres and styles
            genres = [g.strip() for g in self.genre_input.text().split(';')]
            release_metadata['genre'] = genres

        if self.label_input.text().strip():
            labels = [l.strip() for l in self.label_input.text().split(',')]
            release_metadata['labels'] = labels

        if self.catalog_number_input.text().strip():
            catalog_numbers = [c.strip()
                               for c in self.catalog_number_input.text().split(',')]
            release_metadata['catalog_number'] = catalog_numbers

        is_dry_run = self.dry_run_checkbox.isChecked()

        # Prepare summary for confirmation
        confirm_msg = (
            f"**[DRY RUN] Preview metadata for {len(self.loaded_tracks)} file(s)**\n\n"
            if is_dry_run else
            f"**Apply metadata to {len(self.loaded_tracks)} file(s)**\n\n"
        )
        confirm_msg += "**Release-level metadata (applied to all files):**\n"
        for key, value in release_metadata.items():
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            confirm_msg += f"  • {key}: {value}\n"

        # Show track-specific changes
        track_changes = []
        for track_info in self.loaded_tracks:
            filename = track_info["file_path"].split("\\")[-1]
            edited_track_num = track_info.get("edited_track_number")
            edited_title = track_info.get("edited_title")
            edited_composer = track_info.get("edited_composer")

            if edited_track_num or edited_title or edited_composer:
                change = f"  • {filename}:"
                if edited_track_num:
                    change += f" Track#{edited_track_num}"
                if edited_title:
                    change += f" \"{edited_title}\""
                if edited_composer:
                    change += f" (composer: {edited_composer})"
                track_changes.append(change)

        if track_changes:
            confirm_msg += "\n**Track-specific metadata:**\n"
            confirm_msg += "\n".join(track_changes[:10])  # Limit to first 10
            if len(track_changes) > 10:
                confirm_msg += f"\n  ...and {len(track_changes) - 10} more tracks"

        confirm_msg += "\n\nContinue?"

        reply = QMessageBox.question(
            self,
            "Confirm Metadata Write",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Build per-file metadata (cheap, stays on the main thread)
        file_metadata = []
        for track_info in self.loaded_tracks:
            file_path = track_info["file_path"]

            # Start with release-level metadata
            metadata_to_write = release_metadata.copy()

            # Add track-specific metadata
            edited_track_num = track_info.get("edited_track_number")
            if edited_track_num:
                try:
                    # Try to convert to int if possible
                    metadata_to_write['track_number'] = int(edited_track_num)
                except (ValueError, TypeError):
                    # Keep as string if not numeric
                    metadata_to_write['track_number'] = str(edited_track_num)

            edited_title = track_info.get("edited_title")
            if edited_title:
                metadata_to_write['title'] = edited_title

            edited_composer = track_info.get("edited_composer")
            if edited_composer:
                metadata_to_write['composer'] = edited_composer

            file_metadata.append((file_path, metadata_to_write))

        # Write metadata (and optionally analyze BPM) on a background thread -
        # BPM analysis is CPU-heavy and would otherwise freeze the UI
        self.apply_btn.setEnabled(False)
        self._last_apply_was_dry_run = is_dry_run
        self.apply_status_label.setText(
            "Previewing..." if is_dry_run else "Applying metadata...")

        self.apply_worker = ApplyMetadataWorker(
            file_metadata,
            self.analyze_bpm_checkbox.isChecked(),
            analyze_key=self.analyze_key_checkbox.isChecked(),
            dry_run=is_dry_run)
        self.apply_worker.finished.connect(self.on_apply_metadata_finished)
        self.apply_worker.start()

    def on_apply_metadata_finished(self, success_count: int, errors: list):
        """Handle completion of the metadata/BPM apply worker."""
        self.apply_btn.setEnabled(True)
        is_dry_run = self._last_apply_was_dry_run

        # Show results
        if success_count == len(self.loaded_tracks):
            if is_dry_run:
                self.apply_status_label.setText(
                    f"✓ [DRY RUN] {success_count} file(s) would be updated")
                QMessageBox.information(
                    self,
                    "Dry Run Complete",
                    f"No files were changed. {success_count} file(s) would be updated - "
                    "see the log for details."
                )
                return

            self.apply_status_label.setText(
                f"✓ Successfully updated {success_count} file(s)!")
            QMessageBox.information(
                self,
                "Success",
                f"Metadata has been successfully written to {success_count} file(s)."
            )

            # Reload files to show updated metadata
            file_paths = [t["file_path"] for t in self.loaded_tracks]
            self.loaded_tracks.clear()
            self.load_files(file_paths)

        elif success_count > 0:
            self.apply_status_label.setText(
                f"⚠ Updated {success_count}/{len(self.loaded_tracks)} files")
            QMessageBox.warning(
                self,
                "Partial Success",
                f"Updated {success_count}/{len(self.loaded_tracks)} files.\n\n"
                f"Errors:\n" + "\n".join(errors[:5]) +
                (f"\n...and {len(errors) - 5} more" if len(errors) > 5 else "")
            )
        else:
            self.apply_status_label.setText("✗ Failed to update files")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to write metadata to all files.\n\n" +
                "Errors:\n" + "\n".join(errors[:5]) +
                (f"\n...and {len(errors) - 5} more" if len(errors) > 5 else "")
            )
