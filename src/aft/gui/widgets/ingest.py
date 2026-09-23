"""
Ingest widget for batch importing audio files into the library.
"""
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import QThread, Signal

from aft.ingest import process_directory, IngestReport
from ..constants import DEFAULT_SOURCE_DIR, DEFAULT_DEST_DIR

logger = logging.getLogger(__name__)


class IngestWorker(QThread):
    """Worker thread for ingest operations."""

    progress = Signal(str)  # Progress message
    finished = Signal(object)  # IngestReport
    error = Signal(str)  # Error message

    def __init__(
        self,
        source_dir: str,
        dest_root: str,
        db_path: str,
    ):
        super().__init__()
        self.source_dir = source_dir
        self.dest_root = dest_root
        self.db_path = db_path

    def run(self):
        """Run ingest process."""
        try:
            self.progress.emit(f"Starting ingest from {self.source_dir}")

            # BPM analysis and dry-run preview are handled in the Metadata
            # Tools tab instead
            report = process_directory(
                source_dir=self.source_dir,
                dest_root=self.dest_root,
                db_path=self.db_path,
                analyze_bpm=False,
                dry_run=False,
            )

            self.finished.emit(report)

        except (OSError, RuntimeError, ValueError) as e:
            logger.error("Ingest error: %s", str(e))
            self.error.emit(str(e))


class IngestWidget(QWidget):
    """Widget for running ingest operations."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.worker = None
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()

        # Title
        title = QLabel("<h2>Ingest New Files</h2>")
        layout.addWidget(title)

        # Info label
        info_label = QLabel(
            "<i>Ingest organizes audio files into Artist/Album structure. "
            "Cover art images are automatically moved with the release.</i>"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Source selection mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("<b>Source Type:</b>"))
        self.mode_group = QButtonGroup()
        self.dir_radio = QRadioButton("Directory (scan recursively)")
        self.release_radio = QRadioButton("Single Release Folder")
        self.dir_radio.setChecked(True)
        self.mode_group.addButton(self.dir_radio)
        self.mode_group.addButton(self.release_radio)
        mode_layout.addWidget(self.dir_radio)
        mode_layout.addWidget(self.release_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Source directory
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source Path:"))
        self.source_input = QLineEdit(DEFAULT_SOURCE_DIR)
        source_layout.addWidget(self.source_input)
        source_btn = QPushButton("Browse...")
        source_btn.clicked.connect(self.browse_source)
        source_layout.addWidget(source_btn)
        layout.addLayout(source_layout)

        # Destination directory
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination Directory:"))
        self.dest_input = QLineEdit(DEFAULT_DEST_DIR)
        dest_layout.addWidget(self.dest_input)
        dest_btn = QPushButton("Browse...")
        dest_btn.clicked.connect(self.browse_dest)
        dest_layout.addWidget(dest_btn)
        layout.addLayout(dest_layout)

        # Control buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Ingest")
        self.start_btn.clicked.connect(self.start_ingest)
        button_layout.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_ingest)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Log
        layout.addWidget(QLabel("<h3>Log</h3>"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.setLayout(layout)

    def browse_source(self):
        """Browse for source directory or release folder."""
        if self.release_radio.isChecked():
            # Single release folder selection
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select Release Folder")
        else:
            # Full directory scan
            dir_path = QFileDialog.getExistingDirectory(
                self, "Select Source Directory")
        
        if dir_path:
            self.source_input.setText(dir_path)

    def set_source_release(self, path: str):
        """Pre-fill the source path as a single release folder.

        Used by the Metadata Tools tab's "Send to Batch Ingest" handoff so
        the user doesn't have to re-browse for a folder they just worked in.
        """
        self.release_radio.setChecked(True)
        self.source_input.setText(path)

    def browse_dest(self):
        """Browse for destination directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Destination Directory")
        if dir_path:
            self.dest_input.setText(dir_path)

    def start_ingest(self):
        """Start ingest process."""
        source = self.source_input.text()
        dest = self.dest_input.text()

        if not source or not dest:
            QMessageBox.warning(self, "Missing Information",
                                "Please specify source and destination directories")
            return

        if not Path(source).exists():
            QMessageBox.warning(self, "Invalid Path",
                                f"Source path does not exist: {source}")
            return

        # Check if source is a release folder
        is_release = self.release_radio.isChecked()
        
        if is_release:
            # Validate that the folder contains audio files
            from aft.ingest import AUDIO_EXTENSIONS
            source_path = Path(source)
            audio_files = []
            for ext in AUDIO_EXTENSIONS:
                audio_files.extend(source_path.glob(f'*{ext}'))
            
            if not audio_files:
                QMessageBox.warning(self, "No Audio Files",
                                    f"No audio files found in: {source}")
                return
            
            self.log_text.append(f"Found {len(audio_files)} audio files in release folder")

        # Disable start button, enable cancel
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        self.log_text.append(f"Starting ingest from {source} to {dest}...")

        # Create worker
        self.worker = IngestWorker(
            source_dir=source,
            dest_root=dest,
            db_path=self.db_path,
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)

        self.worker.start()

    def cancel_ingest(self):
        """Cancel ingest process."""
        if self.worker:
            self.worker.terminate()
            self.log_text.append("Ingest cancelled by user")
            self.reset_ui()

    def on_progress(self, message: str):
        """Handle progress update."""
        self.log_text.append(message)

    def on_finished(self, report: IngestReport):
        """Handle ingest completion."""
        self.log_text.append("\n" + report.summary())
        QMessageBox.information(
            self,
            "Ingest Complete",
            f"Processed {report.processed} files\nFailed: {report.failed}"
        )
        self.reset_ui()

    def on_error(self, error: str):
        """Handle ingest error."""
        self.log_text.append(f"ERROR: {error}")
        QMessageBox.critical(self, "Ingest Error",
                             f"An error occurred:\n{error}")
        self.reset_ui()

    def reset_ui(self):
        """Reset UI after ingest."""
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
