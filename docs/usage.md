# Usage Guide

This guide provides practical examples and workflows for using the audio-files-tagging system.

## Table of Contents

- [Installation](#installation)
- [Initial Setup](#initial-setup)
- [Basic Workflows](#basic-workflows)
- [CLI Usage](#cli-usage)
- [GUI Usage](#gui-usage)
- [Python API](#python-api)
- [Troubleshooting](#troubleshooting)

## Installation

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Windows 10+ (tested), macOS, or Linux
- ~500 MB disk space for dependencies

### Install from Source

```bash
# Clone the repository
git clone <repository-url>
cd audio-files-tagging

# Create the environment and install dependencies
uv sync
```

Prefix commands with `uv run`, or activate the environment directly:
```bash
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### Verify Installation

```bash
uv run python -c "from aft.bpm import analyze_and_tag_bpm; print('✓ Installation successful')"
```

## Initial Setup

### 1. Configure Discogs API (Optional)

If you want to use Discogs for metadata enrichment:

1. Get a user token from https://www.discogs.com/settings/developers
2. Create a `.env` file in the project root:

```
DISCOGS_USER_TOKEN=your_token_here
```

This is loaded automatically via `python-dotenv` (`aft.credentials`). Both the CLI's `--use-discogs` flag and the GUI's Discogs Lookup tab read from this token.

### 2. Initialize Database

```bash
# Initialize database with default location (data/library.db)
python -m aft.scripts.scan_library scan "D:\Music Collection" --init

# Or specify custom location
python -m aft.scripts.scan_library scan "D:\Music Collection" --db "my_music.db" --init
```

### 3. Configure Paths

Edit the default paths in CLI scripts or GUI if your directories differ:
- Source: `D:\Soulseek Downloads\complete`
- Destination: `D:\Music Collection`

## Basic Workflows

### Workflow 1: First Time Setup

```bash
# 1. Initialize database
python -m aft.scripts.scan_library scan "D:\Music Collection" --init

# 2. Scan existing library
python -m aft.scripts.scan_library scan "D:\Music Collection"

# 3. Check database
python -m aft.scripts.scan_library query-db --limit 10
```

### Workflow 2: Ingest New Downloads

```bash
# 1. Preview changes (dry run)
python -m aft.scripts.ingest ingest \
    --source "D:\Soulseek Downloads\complete" \
    --dest "D:\Music Collection" \
    --dry-run

# 2. Execute ingest with BPM analysis
python -m aft.scripts.ingest ingest \
    --source "D:\Soulseek Downloads\complete" \
    --dest "D:\Music Collection"

# 3. Update database
python -m aft.scripts.scan_library scan "D:\Music Collection" --incremental
```

### Workflow 3: Analyze BPM for Existing Library

```bash
# Analyze single file
python -m aft.scripts.ingest analyze-bpm "D:\Music Collection\Artist\Album\track.mp3"

# Batch analysis (Python script)
python -c "
from pathlib import Path
from aft.bpm import batch_analyze_bpm

files = list(Path('D:/Music Collection').rglob('*.mp3'))[:100]  # First 100 files
results = batch_analyze_bpm(files, write_tags=True)
print(f'Analyzed {len(results)} files')
"
```

### Workflow 4: Query and Search

```bash
# Find tracks by artist
python -m aft.scripts.scan_library query-db --artist "Daft Punk" --limit 20

# Find tracks in BPM range
python -m aft.scripts.scan_library query-db --bpm-min 120 --bpm-max 130

# Combined query
python -m aft.scripts.scan_library query-db \
    --artist "Beatles" \
    --album "Abbey" \
    --bpm-min 100 \
    --bpm-max 140 \
    --limit 10
```

## CLI Usage

### Scan Library

```bash
# Full scan
python -m aft.scripts.scan_library scan "D:\Music Collection"

# Incremental update (faster)
python -m aft.scripts.scan_library scan "D:\Music Collection" --incremental

# With custom database
python -m aft.scripts.scan_library scan "D:\Music Collection" --db "my_db.db"

# Initialize database first
python -m aft.scripts.scan_library scan "D:\Music Collection" --init
```

### Ingest Files

```bash
# Dry run (preview only)
python -m aft.scripts.ingest ingest \
    --source "D:\Downloads" \
    --dest "D:\Music Collection" \
    --dry-run

# Full ingest with BPM
python -m aft.scripts.ingest ingest \
    --source "D:\Downloads" \
    --dest "D:\Music Collection"

# Skip BPM analysis (faster)
python -m aft.scripts.ingest ingest \
    --source "D:\Downloads" \
    --dest "D:\Music Collection" \
    --skip-bpm

# With Discogs metadata lookup
python -m aft.scripts.ingest ingest \
    --source "D:\Downloads" \
    --dest "D:\Music Collection" \
    --use-discogs
```

### Query Database

```bash
# Query by artist
python -m aft.scripts.scan_library query-db --artist "Radiohead"

# Query by BPM range
python -m aft.scripts.scan_library query-db --bpm-min 140 --bpm-max 150

# Query by album
python -m aft.scripts.scan_library query-db --album "Random Access Memories"

# Limit results
python -m aft.scripts.scan_library query-db --artist "Aphex Twin" --limit 5
```

## GUI Usage

### Launch GUI

```bash
uv run python -m aft.gui.main --db "data/library.db"
```

The window has four tabs: Dashboard, Discogs Lookup, Query, and Ingest. They are independent - loading files in one tab doesn't carry over to another.

### Dashboard Tab

- View library statistics (total tracks, tracks with BPM)
- See recent files
- Click "Refresh Statistics" to update

### Discogs Lookup Tab

1. Load one or more audio files
2. Search Discogs (artist/release fields auto-fill from the first file's tags)
3. Select a matching release from the results
4. Review/edit the auto-populated metadata form (genre and styles are combined into one editable field, semicolon-separated)
5. Confirm to apply metadata to the loaded files

### Ingest Tab

1. Set source directory (Browse or type path)
2. Set destination directory
3. Check "Analyze BPM" if desired
4. Check "Dry Run" to preview changes
5. Click "Start Ingest"
6. Monitor progress in log window

Note: this tab does not perform Discogs lookups - use the Discogs Lookup tab for that, or `--use-discogs` on the CLI.

### Query Tab

1. Enter search criteria:
   - Artist name
   - Album name
   - BPM range
2. Click "Search"
3. View results in table
4. Double-click row to see file path
5. Edit a track's BPM cell directly to correct a wrong detection - it's written straight to the file's tag (values outside 20-300 BPM are rejected)

## Python API

### Basic Usage

```python
from aft.bpm import analyze_and_tag_bpm
from aft.tags import AudioTags, read_audio_tags, write_audio_tags
from aft.db import init_db, scan_library, query
from aft.ingest import process_directory

# Initialize database
init_db("data/library.db")

# Analyze BPM
result = analyze_and_tag_bpm("track.mp3", write_tag=True)
print(f"BPM: {result['bpm']:.2f}, Confidence: {result['confidence']:.2%}")

# Read tags
tags = read_audio_tags("track.mp3")
print(tags['artist'], tags['title'])

# Write tags
write_audio_tags("track.mp3", {
    'artist': 'New Artist',
    'album': 'New Album',
    'bpm': 128
})

# Query database
tracks = query(
    artist="Daft Punk",
    bpm_range=(110, 130),
    limit=50
)
for track in tracks:
    print(f"{track.artist} - {track.title} ({track.bpm} BPM)")

# Process directory
report = process_directory(
    source_dir=r"D:\Downloads",
    dest_root=r"D:\Music Collection",
    db_path="data/library.db",
    dry_run=False
)
print(report.summary())
```

### Advanced: Custom Workflow

```python
from pathlib import Path
from aft.bpm import analyze_and_tag_bpm
from aft.tags import AudioTags
from aft.db.database import SessionLocal
from aft.db.models import Track

# Find all tracks without BPM
session = SessionLocal()
tracks_without_bpm = session.query(Track).filter(Track.bpm.is_(None)).all()

print(f"Found {len(tracks_without_bpm)} tracks without BPM")

# Analyze each track
for track in tracks_without_bpm[:10]:  # Process first 10
    file_path = track.file_path
    
    if Path(file_path).exists():
        try:
            result = analyze_and_tag_bpm(file_path, write_tag=True)
            
            if result['bpm']:
                # Update database
                track.bpm = result['bpm']
                session.commit()
                print(f"✓ {track.title}: {result['bpm']:.2f} BPM")
            else:
                print(f"✗ {track.title}: Could not detect BPM")
        
        except Exception as e:
            print(f"✗ {track.title}: Error - {e}")
    else:
        print(f"✗ {track.title}: File not found")

session.close()
```

### Batch Operations

```python
from pathlib import Path
from aft.bpm import batch_analyze_bpm

# Analyze all MP3 files in a directory
music_dir = Path("D:/Music Collection/Artist/Album")
mp3_files = list(music_dir.glob("*.mp3"))

results = batch_analyze_bpm(mp3_files, write_tags=True)

# Print summary
total = len(results)
successful = sum(1 for r in results if r['bpm'] is not None)
avg_bpm = sum(r['bpm'] for r in results if r['bpm']) / successful if successful > 0 else 0

print(f"Analyzed: {total} files")
print(f"Successful: {successful} ({successful/total*100:.1f}%)")
print(f"Average BPM: {avg_bpm:.2f}")
```

## Troubleshooting

### Common Issues

#### 1. Import Error: Cannot import 'aft'

**Solution**: Make sure you're in the project directory and have installed dependencies:

```bash
cd audio-files-tagging
uv sync
```

#### 2. Database Locked Error

**Solution**: Close any other applications accessing the database:

```python
# Or manually close sessions
from aft.db.database import SessionLocal
session = SessionLocal()
# ... do work ...
session.close()  # Always close when done
```

#### 3. BPM Detection Returns None or Looks Wrong

**Possible causes**:
- File is corrupted
- Audio is too short (< 10 seconds)
- No clear beat/rhythm
- Half/double-tempo (octave) error - detection includes automatic correction for this within a 60-200 BPM plausible range, but very fast (>200 BPM) or very slow (<60 BPM) genres may still be misjudged

**Solution**: Check file integrity, or correct the value directly in the GUI's Query tab (edit the BPM cell - it writes straight to the file's tag).

#### 4. Librosa Installation Issues

**Windows**: May need Visual C++ Build Tools

```bash
# Install from Microsoft or use pre-built wheels
pip install librosa --only-binary :all:
```

#### 5. Permission Errors When Moving Files

**Solution**: Run with administrator privileges or check folder permissions.

### Logging

Enable debug logging for troubleshooting:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/aft_debug.log'),
        logging.StreamHandler()
    ]
)
```

### Performance Tips

1. **Skip BPM for faster ingests**: Use `--skip-bpm` flag
2. **Incremental updates**: Use `--incremental` instead of full scans
3. **Batch operations**: Process files in batches rather than one-by-one
4. **SSD storage**: Store database and library on SSD for faster access

## Getting Help

- Check the [Architecture Documentation](architecture.md) for system design
- Review the [main README](../README.md) for project overview
- Check module docstrings: `python -c "from aft.bpm import analyze_and_tag_bpm; help(analyze_and_tag_bpm)"`
- Open an issue on GitHub for bugs or feature requests
