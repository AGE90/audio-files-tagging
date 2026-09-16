# Quick Start Guide

Get up and running with audio-files-tagging in 5 minutes!

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Windows 10+ (or macOS/Linux)
- Your music collection path (e.g., `D:\Music Collection`)

## Step 1: Install (2 minutes)

```bash
# Navigate to project
cd audio-files-tagging

# Create the environment and install dependencies
uv sync
```

Prefix commands below with `uv run` (e.g. `uv run python -m aft.scripts.ingest ...`), or activate the environment directly: `.\.venv\Scripts\activate` (Windows) / `source .venv/bin/activate` (macOS/Linux).

## Step 2: Initialize Database (30 seconds)

```bash
python -m aft.scripts.scan_library scan "D:\Music Collection" --init --db "data/library.db"
```

## Step 3: Choose Your Interface

### Option A: GUI (Recommended for Beginners)

```bash
python -m aft.gui.main --db "data/library.db"
```

Then:
1. Go to "Ingest" tab
2. Set source: `D:\Soulseek Downloads\complete`
3. Set destination: `D:\Music Collection`
4. Check "Dry Run" to preview
5. Click "Start Ingest"

### Option B: CLI (For Power Users)

```bash
# Preview what will happen (dry run)
python -m aft.scripts.ingest ingest \
    --source "D:\Soulseek Downloads\complete" \
    --dest "D:\Music Collection" \
    --dry-run

# Actually process files
python -m aft.scripts.ingest ingest \
    --source "D:\Soulseek Downloads\complete" \
    --dest "D:\Music Collection"
```

## Step 4: Scan Your Library (1 minute)

```bash
python -m aft.scripts.scan_library scan "D:\Music Collection"
```

## Step 5: Query Your Music (10 seconds)

```bash
# Find tracks by artist
python -m aft.scripts.scan_library query-db --artist "Daft Punk"

# Find tracks in BPM range
python -m aft.scripts.scan_library query-db --bpm-min 120 --bpm-max 130 --limit 20
```

## Common Tasks

### Analyze BPM for a Single File

```bash
python -m aft.scripts.ingest analyze-bpm "path/to/track.mp3"
```

### Update Library After Manual Changes

```bash
# Only scan new/modified files (fast)
python -m aft.scripts.scan_library scan "D:\Music Collection" --incremental
```

### Batch BPM Analysis (Python)

```python
from pathlib import Path
from aft.bpm import batch_analyze_bpm

files = list(Path("D:/Music Collection/Artist/Album").glob("*.mp3"))
results = batch_analyze_bpm(files, write_tags=True)

print(f"Analyzed {len(results)} files")
```

## Daily Workflow

1. **Download music** → `D:\Soulseek Downloads\complete`
2. **Run ingest**: 
   ```bash
   python -m aft.scripts.ingest ingest --source "D:\Soulseek Downloads\complete" --dest "D:\Music Collection"
   ```
3. **Files are**:
   - Analyzed for BPM
   - Tagged with metadata
   - Moved to `D:\Music Collection\Artist\Album\Track.mp3`
   - Added to database

## Troubleshooting

### "Cannot import aft"
→ Make sure you're in the project directory and use `uv run`, or activate the venv:
```bash
cd audio-files-tagging
uv run python -m aft.scripts.ingest --help
```

### "Database is locked"
→ Close GUI or other programs accessing the database

### "BPM detection returns None"
→ File may be too short or have no clear beat. Skip or enter manually.

## What's Next?

- Read the [Usage Guide](docs/usage.md) for detailed examples
- Check [Architecture](docs/architecture.md) to understand the system
- Browse the [Project Summary](PROJECT_SUMMARY.md) for what's been built

## Getting Help

- Check docstrings: `python -c "from aft.bpm import analyze_and_tag_bpm; help(analyze_and_tag_bpm)"`
- Review test files in `tests/` for usage examples
- Open an issue if you find bugs

---

**That's it! You're ready to organize your music collection! 🎵**
