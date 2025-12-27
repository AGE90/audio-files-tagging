"""
Constants for the GUI application.

Centralized configuration values for window sizes, default paths,
colors, and other application-wide settings.
"""

# Window Configuration
WINDOW_TITLE = "Audio Metadata Tag Editor - Music Library Manager"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
WINDOW_X = 100
WINDOW_Y = 100

# Default Paths
DEFAULT_DB_PATH = "data/library.db"
DEFAULT_SOURCE_DIR = r"D:\Soulseek Downloads\complete"
DEFAULT_DEST_DIR = r"D:\Music Collection"

# Table Configuration
TABLE_COLUMN_WIDTH_PATH = 300
TABLE_COLUMN_WIDTH_DEFAULT = 100

# Dashboard Table Columns
DASHBOARD_COLUMNS = [
    "Title", "Artist", "Album Artist", "Album", "Track #", "Disc #",
    "Year", "Genre", "Key", "BPM", "Duration", "Bitrate",
    "Sample Rate", "Publisher", "Catalog #", "Path"
]

# Query Results Table Columns
QUERY_RESULTS_COLUMNS = ["Title", "Artist", "Album", "BPM", "Path"]

# Discogs Results Table Columns
DISCOGS_RESULTS_COLUMNS = ["ID", "Title", "Artist", "Year", "Format"]

# BPM Configuration
BPM_MIN_DEFAULT = 0
BPM_MAX_DEFAULT = 200
BPM_RANGE_MIN = 0
BPM_RANGE_MAX = 300

# Search Configuration
SEARCH_MAX_RESULTS = 100
DISCOGS_MAX_RESULTS = 20

# Audio File Extensions
AUDIO_FILE_FILTER = "Audio Files (*.mp3 *.flac *.m4a *.mp4 *.ogg);;All Files (*.*)"

# UI Text Heights
TEXT_EDIT_HEIGHT_SMALL = 150
TEXT_EDIT_HEIGHT_MEDIUM = 200

# Status Messages
STATUS_READY = "Ready"
STATUS_DISCOGS_CONNECTED = "✓ Connected to Discogs API"
STATUS_DISCOGS_NO_TOKEN = "⚠ No Discogs API token found. Set DISCOGS_USER_TOKEN in .env file"
STATUS_DISCOGS_ERROR = "⚠ Error initializing Discogs: {}"
STATUS_METADATA_SUCCESS = "✓ Metadata successfully applied!"
STATUS_METADATA_FAILED = "✗ Failed to apply metadata"
STATUS_METADATA_ERROR = "✗ Error: {}"

# Application Style
APP_STYLE = "Fusion"

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = "INFO"
