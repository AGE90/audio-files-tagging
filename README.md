# 1) Project description and deliverables
You have access to the full codebase of the **audio-files-tagging** project.
This project organizes my music collection and processes new incoming records located in:

```
D:\Soulseek Downloads\complete
```

The *destination* and main library structure is:

```
D:\Music Collection\<artist-name>\<release-album-name>\<track>
```

Repository contains a Jupyter notebook:

```
AGE90-audio_files_tagging.ipynb
```

and the Python package under:

```
audio-files-tagging/src/aft
```

I want you to extend, refactor, and improve the project with the following deliverables.

## Goals

1. Robust BPM detection and writing BPM into track metadata.
2. Build and maintain a music library database (SQLite).
3. Ingest pipeline for `D:\Soulseek Downloads\complete` → process → move to `D:\Music Collection\...` and update DB.
4. A GUI (desktop app preferred for offline/local file access) to let the user run the ingest, scan, tagging, search, and repair operations.
5. Refactor & improve existing code and notebook.
6. Produce a README and an architecture diagram (both included below).

## Required features & API surface

### BPM analyzer

* Accurate BPM detection (works for a wide range of tempos; robust to slight tempo drift).
* Write BPM into tags (ID3v2/BWF/FLAC/Vorbis/MP4 as appropriate).
* Public function:

```py
from aft.bpm import analyze_and_tag_bpm
analyze_and_tag_bpm(file_path: str, write_tag: bool = True) -> dict
# returns dict: { 'file_path':..., 'bpm':..., 'confidence':..., 'duration':..., 'samples':... }
```

### Library database

* SQLite DB with tracks table: (id, artist, album, title, year, genre, bpm, duration, bitrate, sample_rate, path, tags_json, last_modified).
* Modules:

  * `aft.db.scan_library(base_path: str) -> None` — full scan.
  * `aft.db.incremental_update(base_path: str) -> list` — detect new/changed files.
  * `aft.db.query(**kwargs) -> List[TrackRecord]` — query helper (artist, bpm_range, year, tags, text search).
* Expose CLI and programmatic usage.

### Ingest pipeline

* Pipeline steps:

  1. Detect new files in `D:\Soulseek Downloads\complete` (by monitoring or manual run).
  2. Normalize filenames and directories (optionally parse tags to derive artist/album/title).
  3. Analyze metadata + BPM + any other analytics (key detection optional).
  4. Write cleaned tags.
  5. Move to `D:\Music Collection\<artist>\<album>\<track>`.
  6. Update DB.
* API:

```py
aft.ingest.process_directory(source_dir: str, dest_root: str, dry_run: bool=False) -> Report
```

### GUI

* Desktop app that can run on Windows and operate on local files.
* Features:

  * Dashboard: recent ingested files, ingest progress, last scan results.
  * Manual ingest/scan controls and scheduling option.
  * Per-track view: tags, waveform preview, BPM value with re-analyze button.
  * Batch operations: re-tag, rewrite tags, move, update DB.
  * Query & filters: search by artist, BPM range, duration, tags.
  * Log/Task view showing success/fail for each file.
* Suggested stacks (pick one in implementation): PySide6 (Qt for Python) or Tauri/Electron with Python backend (FastAPI). I recommend **PySide6** for a pure-Python desktop app (simple packaging with PyInstaller, direct file system access, no separate frontend build).

### Refactor & quality

* Add typing, docstrings, and unit tests for core functions.
* Centralize audio IO (one module to read/write tags/audio features).
* Logging and clear error handling.
* Notebook cleaned and converted into a repeatable script where appropriate (e.g., `scripts/demo_bpm_analysis.py`).

## Output expectations from the assistant

* Reference specific files/functions to change.
* Provide revised versions of functions/modules (inline or as patches).
* Provide README and architecture diagram.
* Provide example usage code and CLI commands.

---

# 2) README (ready to drop into repo as README.md)

````markdown
# audio-files-tagging

Organize and tag a personal music collection.  
Processes new downloads, analyzes BPM, writes tags, and maintains a searchable library DB.

## Overview

- **Source (incoming):** `D:\Soulseek Downloads\complete`
- **Main library:** `D:\Music Collection\<artist-name>\<release-album-name>\<track>`
- **Package:** `audio-files-tagging/src/aft`
- **Notebook:** `AGE90-audio_files_tagging.ipynb`

Features:
- BPM detection and tagging
- Persistent SQLite library database
- Ingest pipeline: detect → analyze → tag → move → DB update
- Desktop GUI to run and monitor processes
- CLI tools and headless APIs

## Quick start (Windows)

1. Clone the repository.
2. Create a venv and install:
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
````

3. Run a full scan (dry run first):

```bash
python -m aft.scripts.scan_library --root "D:\Music Collection" --db "data/library.db" --dry-run
```

4. Ingest new downloads:

```bash
python -m aft.scripts.ingest --source "D:\Soulseek Downloads\complete" --dest "D:\Music Collection" --db "data/library.db"
```

5. Start GUI (if using PySide6 UI):

```bash
python -m aft.gui.main --db "data/library.db"
```

## Modules & CLI

* `aft.bpm` — BPM detection helpers and tag writing.
* `aft.tags` — Unified tag read/write for MP3/FLAC/M4A/OGG.
* `aft.db` — Database models, scan, and query utilities.
* `aft.ingest` — Full ingest pipeline (clean → analyze → tag → move → update DB).
* `aft.gui` — Desktop application (PySide6).
* `aft.scripts` — CLI wrappers using Typer.

### Example usage (programmatic)

```py
from aft.ingest import process_directory
report = process_directory(
    source_dir=r"D:\Soulseek Downloads\complete",
    dest_root=r"D:\Music Collection",
    db_path="data/library.db",
    dry_run=False
)
print(report.summary())
```

## Architecture

(See `docs/architecture.md` for a diagram and explanation.)

## Development notes

* Use `pytest` for unit tests:

```bash
pytest tests/
```

* Run linting with `ruff` / `black`.
* Tests and CI should validate tag read/write, BPM detection on sample audio, and DB updates.

## Design decisions & recommendations

* **Database:** SQLite for portability. Use SQLAlchemy for models.
* **BPM:** Use `librosa` or `essentia` for BPM detection. Provide fallback: `aubio` for fast detection.
* **Tagging:** Use `mutagen` for cross-format tag writing.
* **GUI:** PySide6 recommended for native desktop GUI with direct filesystem access.

````

---

# 3) Architecture diagram (Mermaid + textual explanation)

Paste this mermaid into `docs/architecture.md` or any Markdown renderer that supports mermaid.

```mermaid
flowchart TD
  subgraph INCOMING
    A[Downloads Folder: D:\Soulseek Downloads\complete]
  end

  subgraph INGEST_PIPELINE
    B1[File Watcher / Scanner]
    B2[Metadata Cleaner]
    B3[BPM Analyzer]
    B4[Tag Writer]
    B5[File Mover]
    B6[DB Updater]
  end

  subgraph LIBRARY
    C1["D:\Music Collection\<Artist>\<Album>\<Track>"]
    C2[(SQLite DB)]
  end

  subgraph GUI
    G1[Dashboard]
    G2[Manual Ingest / Controls]
    G3[Search & Query]
    G4[Track Detail]
    G5[Logs / Tasks]
  end

  subgraph CLI_API
    H1[CLI (Typer)]
    H2[API (FastAPI optional)]
  end

  A --> B1
  B1 --> B2 --> B3 --> B4 --> B5 --> B6
  B5 --> C1
  B6 --> C2

  C2 -->|read/write| G1
  G2 --> B1
  G3 --> C2
  G4 --> C1 & C2
  H1 --> B1
  H2 --> B1
````

**Short explanation**

* **File Watcher / Scanner:** detects new files (or runs as manual job).
* **Metadata Cleaner:** normalizes tags and file naming.
* **BPM Analyzer:** computes BPM and confidence; may use `librosa`, `essentia`, or `aubio`.
* **Tag Writer:** writes to file tags with `mutagen`.
* **File Mover:** places files into `D:\Music Collection\<artist>\<album>\<track>`.
* **DB Updater:** persists metadata and file state into SQLite.
* **GUI / CLI / API:** control and monitor pipeline; GUI is desktop-first for file access.

---

# 4) GUI options & recommendation

**Option A — PySide6 (recommended)**

* Pure Python, single process, direct file system access.
* Pros: simple packaging for Windows (PyInstaller), single codebase, no CORS or cross-process complexity.
* Cons: native look depends on Qt; larger binary.

**Option B — FastAPI (backend) + React/Electron/ Tauri (frontend)**

* Pros: modern UI, web technologies, reusable API for other apps.
* Cons: requires packaging backend & frontend; heavier stack.

**Recommended stack**: **PySide6** for initial implementation, because your workflow is primarily local files on Windows. If you later want remote access, add a light FastAPI server and React frontend.

**Minimal UI screens**

1. **Dashboard** — recent ingest history, stats (tracks, avg BPM), start/stop ingest.
2. **Ingest Wizard** — pick source & destination, dry run toggle, start ingest.
3. **Track List / Query** — filters (artist, BPM range, year), sortable list.
4. **Track Detail** — tags, waveform thumbnail, BPM value, re-analyze, re-tag buttons.
5. **Task/Log Viewer** — shows ingest steps & errors.

---

# 5) Proposed repository layout

```
audio-files-tagging/
├─ src/
│  └─ aft/
│     ├─ __init__.py
│     ├─ bpm.py                # BPM detection & analysis
│     ├─ tags.py               # read/write tags (mutagen wrapper)
│     ├─ audio_io.py           # load audio segments, duration
│     ├─ ingest.py             # orchestrates ingest pipeline
│     ├─ db.py                 # SQLite models and queries (SQLAlchemy)
│     ├─ utils.py              # helpers: path parsing, normalization
│     ├─ gui/
│     │  ├─ main.py            # entrypoint for PySide6 app
│     │  └─ widgets/           # UI components
│     └─ scripts/
│        ├─ scan_library.py
│        └─ ingest.py
├─ data/
│  └─ library.db
├─ docs/
│  ├─ architecture.md
│  └─ README.md
├─ tests/
│  └─ test_bpm.py
├─ AGE90-audio_files_tagging.ipynb
├─ requirements.txt
├─ pyproject.toml
└─ README.md
```

---

# 6) Example CLI / script signatures

**CLI using Typer**

```py
# src/aft/scripts/ingest.py
import typer
from aft.ingest import process_directory

app = typer.Typer()

@app.command()
def ingest(source: str, dest: str, db: str = "data/library.db", dry_run: bool = True):
    report = process_directory(source, dest, db_path=db, dry_run=dry_run)
    print(report.summary())

if __name__ == "__main__":
    app()
```

**Scan**

```bash
python -m aft.scripts.scan_library --root "D:\Music Collection" --db "data/library.db" --dry-run
```

**Run GUI**

```bash
python -m aft.gui.main --db "data/library.db"
```

---

# 7) Testing & dependencies suggestions

* Python >= 3.10
* Key libs:

  * `mutagen` for tag read/write
  * `librosa` or `essentia` or `aubio` for BPM detection (librosa easier to install; Essentia stronger for quality)
  * `sqlalchemy` for DB model
  * `PySide6` for GUI (or `PyQt6`)
  * `typer` for CLI
* Testing: `pytest` + small audio fixtures (very short clips) to validate BPM detection and tag writing.

---

# 8) Next steps I can produce right now (pick any and I’ll generate immediately):

* Full `README.md` file (I already provided a draft — I can expand it into a full repo README).
* Detailed `aft/bpm.py` scaffold with code using `librosa` and `mutagen` (ready-to-run).
* `aft/ingest.py` pipeline scaffold with concrete implementation.
* `aft/db.py` SQLAlchemy models and scan implementation.
* PySide6 GUI skeleton (main window + a few widgets).
* Unit test examples for BPM detection and DB updates.
* A rendered PNG of the architecture diagram (note: I can provide mermaid text; I cannot render images directly here).

I included the README and a mermaid architecture diagram above so you can add them to the repo immediately. If you want, I’ll now generate one of the code scaffolds (BPM module, DB model, or GUI skeleton) — tell me which and I’ll produce the code now.
