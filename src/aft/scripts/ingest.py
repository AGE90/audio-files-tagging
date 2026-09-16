"""
CLI script for ingesting new music files.

Usage:
    python -m aft.scripts.ingest ingest --source "D:\\Soulseek Downloads\\complete" --dest "D:\\Music Collection"
    python -m aft.scripts.ingest ingest --source "D:\\Soulseek Downloads\\complete" --dest "D:\\Music Collection" --dry-run
"""
import logging
import typer
from pathlib import Path

from aft.ingest import process_directory
from aft.credentials import discogs_user_token
from aft.discogs_client import DiscogsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = typer.Typer(help="Ingest new music files into organized library")


@app.command()
def ingest(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        help="Source directory with new music files"
    ),
    dest: str = typer.Option(
        ...,
        "--dest",
        "-d",
        help="Destination root directory for organized library"
    ),
    db: str = typer.Option(
        "data/library.db",
        "--db",
        help="Path to SQLite database file"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Simulate without making actual changes"
    ),
    skip_bpm: bool = typer.Option(
        False,
        "--skip-bpm",
        help="Skip BPM analysis (faster)"
    ),
    use_discogs: bool = typer.Option(
        False,
        "--use-discogs",
        help="Use Discogs API for metadata lookup (requires token)"
    ),
) -> None:
    """
    Ingest new music files into organized library.
    
    This will:
    1. Find all audio files in the source directory
    2. Normalize filenames and metadata
    3. Analyze BPM (unless --skip-bpm)
    4. Move files to organized structure: dest/artist/album/track
    5. Update database
    
    Examples:
    
        # Dry run to preview changes
        python -m aft.scripts.ingest \\
            --source "D:\\Soulseek Downloads\\complete" \\
            --dest "D:\\Music Collection" \\
            --dry-run
        
        # Full ingest with BPM analysis
        python -m aft.scripts.ingest \\
            --source "D:\\Soulseek Downloads\\complete" \\
            --dest "D:\\Music Collection"
        
        # Skip BPM analysis (faster)
        python -m aft.scripts.ingest \\
            --source "D:\\Soulseek Downloads\\complete" \\
            --dest "D:\\Music Collection" \\
            --skip-bpm
    """
    source_path = Path(source)
    dest_path = Path(dest)
    
    # Validate paths
    if not source_path.exists():
        typer.secho(f"Error: Source directory does not exist: {source}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    if not dry_run and not dest_path.exists():
        typer.secho(f"Destination directory does not exist: {dest}", fg=typer.colors.YELLOW)
        create = typer.confirm("Create destination directory?")
        if create:
            dest_path.mkdir(parents=True, exist_ok=True)
            typer.secho(f"Created destination directory: {dest}", fg=typer.colors.GREEN)
        else:
            raise typer.Exit(code=1)
    
    # Initialize Discogs client if requested
    discogs_client = None
    if use_discogs:
        if discogs_user_token:
            typer.secho("Initializing Discogs client...", fg=typer.colors.YELLOW)
            discogs_client = DiscogsClient(user_token=discogs_user_token)
        else:
            typer.secho(
                "Warning: Discogs token not found. Skipping Discogs lookup.",
                fg=typer.colors.YELLOW
            )
    
    # Start ingest
    try:
        if dry_run:
            typer.secho("\n*** DRY RUN MODE - No changes will be made ***\n", fg=typer.colors.YELLOW, bold=True)
        
        typer.secho(f"Starting ingest from {source} to {dest}...", fg=typer.colors.CYAN)
        
        report = process_directory(
            source_dir=str(source_path),
            dest_root=str(dest_path),
            db_path=db if not dry_run else None,
            analyze_bpm=not skip_bpm,
            dry_run=dry_run,
            discogs_client=discogs_client,
        )
        
        # Display report
        typer.secho("\n" + "=" * 60, fg=typer.colors.BLUE)
        typer.secho(report.summary(), fg=typer.colors.GREEN)
        
        # Show failed files if any
        if report.failed > 0:
            typer.secho("\nFailed files:", fg=typer.colors.RED, bold=True)
            for result in report.results:
                if not result.success:
                    typer.secho(f"  - {result.file_path}: {result.message}", fg=typer.colors.RED)

        # Flag low-confidence BPM detections for manual review (still written
        # to the tag, per the flag-don't-block policy - see aft.bpm).
        low_confidence_results = [
            r for r in report.results
            if r.success and r.metadata
            and r.metadata.get('bpm_confidence') is not None
            and r.metadata['bpm_confidence'] < 0.5
        ]
        if low_confidence_results:
            typer.secho("\nLow-confidence BPM detections (review recommended):", fg=typer.colors.YELLOW, bold=True)
            for result in low_confidence_results:
                metadata = result.metadata or {}
                typer.secho(
                    f"  - {result.new_path or result.file_path}: "
                    f"BPM {metadata['bpm']} (confidence {metadata['bpm_confidence']:.0%})",
                    fg=typer.colors.YELLOW,
                )

        # Success message
        if report.processed > 0:
            if dry_run:
                typer.secho(
                    f"\n✓ Dry run complete. Would process {report.processed} files.",
                    fg=typer.colors.GREEN,
                    bold=True
                )
            else:
                typer.secho(
                    f"\n✓ Ingest complete! Processed {report.processed} files.",
                    fg=typer.colors.GREEN,
                    bold=True
                )
        else:
            typer.secho("\nNo files were processed.", fg=typer.colors.YELLOW)
    
    except Exception as e:
        typer.secho(f"\nError during ingest: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def analyze_bpm(
    file_path: str = typer.Argument(..., help="Path to audio file"),
    write: bool = typer.Option(
        True,
        "--write/--no-write",
        help="Write BPM to file tags"
    ),
) -> None:
    """
    Analyze BPM of a single audio file.
    
    Example:
    
        python -m aft.scripts.ingest analyze-bpm "track.mp3"
    """
    from aft.bpm import analyze_and_tag_bpm
    
    file = Path(file_path)
    
    if not file.exists():
        typer.secho(f"Error: File does not exist: {file_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    try:
        typer.secho(f"Analyzing BPM for {file.name}...", fg=typer.colors.YELLOW)
        
        result = analyze_and_tag_bpm(str(file), write_tag=write)
        
        if result['bpm']:
            typer.secho(f"\nResults:", fg=typer.colors.GREEN, bold=True)
            typer.secho(f"  BPM: {result['bpm']:.2f}")
            typer.secho(f"  Confidence: {result['confidence']:.2%}")
            typer.secho(f"  Duration: {result['duration']:.2f}s")
            
            if write:
                typer.secho(f"\n✓ BPM written to file tags", fg=typer.colors.GREEN)
        else:
            typer.secho("Could not detect BPM", fg=typer.colors.RED)
    
    except Exception as e:
        typer.secho(f"Error analyzing BPM: {str(e)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
