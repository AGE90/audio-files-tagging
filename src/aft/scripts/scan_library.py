"""
CLI script for scanning music library and updating database.

Usage:
    python -m aft.scripts.scan_library scan "D:\\Music Collection" --db "data/library.db"
    python -m aft.scripts.scan_library scan "D:\\Music Collection" --incremental
"""
import logging
from pathlib import Path
from typing import Optional

import typer

from aft.db.database import incremental_update, init_db, scan_library, query

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = typer.Typer(help="Scan music library and update database")


@app.command()
def scan(
    root: str = typer.Argument(help="Root directory of music library to scan"),
    db: str = typer.Option(
        "data/library.db",
        "--db",
        "-d",
        help="Path to SQLite database file"
    ),
    incremental: bool = typer.Option(
        False,
        "--incremental",
        "-i",
        help="Perform incremental update (only new/modified files)"
    ),
    init: bool = typer.Option(
        False,
        "--init",
        help="Initialize database before scanning"
    ),
) -> None:
    """
    Scan music library and update database.

    This will recursively scan all audio files in the specified directory
    and add/update them in the database with metadata.

    Examples:

        # Full scan with database initialization
        python -m aft.scripts.scan_library scan "D:\\Music Collection" --init

        # Incremental update (faster)
        python -m aft.scripts.scan_library scan "D:\\Music Collection" --incremental

        # Custom database location
        python -m aft.scripts.scan_library scan "D:\\Music Collection" --db "my_music.db"
    """
    root_path = Path(root)

    if not root_path.exists():
        typer.secho(
            f"Error: Directory does not exist: {root}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Initialize database if requested
    if init:
        typer.secho(
            f"Initializing database at {db}...", fg=typer.colors.YELLOW)
        init_db(db)
        typer.secho("Database initialized", fg=typer.colors.GREEN)

    # Perform scan
    try:
        if incremental:
            typer.secho(
                f"Starting incremental update of {root}...", fg=typer.colors.YELLOW)
            updated_files = incremental_update(str(root_path), db)
            typer.secho(
                f"Incremental update complete. Updated {len(updated_files)} files.",
                fg=typer.colors.GREEN
            )
        else:
            typer.secho(
                f"Starting full scan of {root}...", fg=typer.colors.YELLOW)
            scan_library(str(root_path), db)
            typer.secho("Full scan complete", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Error during scan: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def query_db(
    db: str = typer.Option(
        "data/library.db",
        "--db",
        "-d",
        help="Path to SQLite database file"
    ),
    artist: Optional[str] = typer.Option(
        None,
        "--artist",
        "-a",
        help="Filter by artist name"
    ),
    album: Optional[str] = typer.Option(
        None,
        "--album",
        help="Filter by album name"
    ),
    bpm_min: Optional[float] = typer.Option(
        None,
        "--bpm-min",
        help="Minimum BPM"
    ),
    bpm_max: Optional[float] = typer.Option(
        None,
        "--bpm-max",
        help="Maximum BPM"
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of results"
    ),
) -> None:
    """
    Query the music library database.

    Examples:

        # Find tracks by artist
        python -m aft.scripts.scan_library query-db --artist "Daft Punk"

        # Find tracks in BPM range
        python -m aft.scripts.scan_library query-db --bpm-min 120 --bpm-max 130

        # Combined query
        python -m aft.scripts.scan_library query-db --artist "Beatles" --album "Abbey" --limit 10
    """
    try:
        # Build BPM range if both limits provided
        bpm_range = None
        if bpm_min is not None and bpm_max is not None:
            bpm_range = (bpm_min, bpm_max)

        # Query database
        results = query(
            artist=artist,
            album=album,
            bpm_range=bpm_range,
            limit=limit,
            db_path=db
        )

        if not results:
            typer.secho("No results found", fg=typer.colors.YELLOW)
            return

        # Display results
        typer.secho(f"\nFound {len(results)} tracks:", fg=typer.colors.GREEN)
        typer.secho("=" * 80, fg=typer.colors.BLUE)

        for i, track in enumerate(results, 1):
            artist_name = track.artist or "Unknown Artist"
            album_name = track.album or "Unknown Album"
            bpm_str = f"{track.bpm:.1f}" if track.bpm is not None else "N/A"

            typer.secho(f"{i}. {track.title}", fg=typer.colors.CYAN, bold=True)
            typer.secho(
                f"   Artist: {artist_name} | Album: {album_name} | BPM: {bpm_str}")
            typer.secho(f"   Path: {track.file_path}", dim=True)
            typer.secho("")

    except Exception as e:
        typer.secho(f"Error querying database: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
