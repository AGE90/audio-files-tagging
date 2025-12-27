"""
Ingest pipeline for processing new music files.

Orchestrates the full workflow:
1. Detect new files
2. Normalize filenames and directories
3. Analyze metadata and BPM
4. Write cleaned tags
5. Move to organized library
6. Update database
"""
import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from aft.tags import read_audio_tags
from aft.bpm import analyze_and_tag_bpm
from aft.utils.normalization import normalize_spaces
from aft.db.database import get_session_factory, SessionLocal, Track
from aft.discogs_client import DiscogsClient

logger = logging.getLogger(__name__)

# Audio file extensions to process
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}


@dataclass
class FileProcessingResult:
    """Result of processing a single file."""
    file_path: str
    success: bool
    message: str
    new_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IngestReport:
    """
    Report of ingest pipeline execution.

    Attributes
    ----------
    source_dir : str
        Source directory that was processed
    dest_root : str
        Destination root directory
    total_files : int
        Total number of files found
    processed : int
        Number of files successfully processed
    failed : int
        Number of files that failed
    skipped : int
        Number of files skipped
    results : List[FileProcessingResult]
        Detailed results for each file
    dry_run : bool
        Whether this was a dry run (no actual changes made)
    """
    source_dir: str
    dest_root: str
    total_files: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[FileProcessingResult] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        """Generate a summary string of the report."""
        status = "DRY RUN - " if self.dry_run else ""
        success_rate = (self.processed / self.total_files * 100) if self.total_files > 0 else 0

        lines = [
            f"{status}Ingest Report",
            "=" * 50,
            f"Source: {self.source_dir}",
            f"Destination: {self.dest_root}",
            f"Total Files: {self.total_files}",
            f"Processed: {self.processed}",
            f"Failed: {self.failed}",
            f"Skipped: {self.skipped}",
            f"Success Rate: {success_rate:.1f}%",
        ]

        return "\n".join(lines)


def normalize_filename(filename: str) -> str:
    """
    Normalize a filename by removing illegal characters and extra spaces.

    Parameters
    ----------
    filename : str
        Original filename

    Returns
    -------
    str
        Normalized filename safe for filesystem
    """
    # Remove illegal characters for Windows filesystems
    illegal_chars = '<>:"|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '')

    # Normalize spaces
    filename = normalize_spaces(filename)

    # Replace multiple dots (except extension)
    parts = filename.rsplit('.', 1)
    if len(parts) == 2:
        name, ext = parts
        name = name.replace('..', '.').strip('.')
        filename = f"{name}.{ext}"

    return filename


def detect_artist_album_from_path(
    file_path: Path,
    source_dir: Path
) -> tuple[Optional[str], Optional[str]]:
    """
    Try to detect artist and album from directory structure.

    Assumes structure like: source_dir / [artist - album] / track
    or: source_dir / artist / album / track

    Parameters
    ----------
    file_path : Path
        Path to the audio file
    source_dir : Path
        Root source directory

    Returns
    -------
    tuple[Optional[str], Optional[str]]
        (artist, album) or (None, None) if cannot detect
    """
    try:
        # Get relative path parts
        relative = file_path.relative_to(source_dir)
        parts = relative.parts[:-1]  # Exclude filename

        if len(parts) == 0:
            return None, None

        if len(parts) == 1:
            # Single folder - try to parse "Artist - Album" format
            folder = parts[0]
            if ' - ' in folder:
                artist, album = folder.split(' - ', 1)
                return normalize_spaces(artist), normalize_spaces(album)

            # Just album or artist?
            return None, normalize_spaces(folder)

        if len(parts) >= 2:
            # Multiple folders: artist / album / ...
            artist = normalize_spaces(parts[0])
            album = normalize_spaces(parts[1])
            return artist, album

    except (ValueError, OSError) as e:
        logger.debug(
            "Could not detect artist/album from path %s: %s", file_path, e)

    return None, None


def process_audio_file(
    file_path: Path,
    source_dir: Path,
    dest_root: Path,
    analyze_bpm: bool = True,
    dry_run: bool = False,
    discogs_client: Optional[DiscogsClient] = None,
) -> FileProcessingResult:
    """
    Process a single audio file through the ingest pipeline.

    Parameters
    ----------
    file_path : Path
        Path to the audio file to process
    source_dir : Path
        Root source directory
    dest_root : Path
        Root destination directory
    analyze_bpm : bool
        Whether to analyze and write BPM
    dry_run : bool
        If True, don't make any actual changes
    discogs_client : Optional[DiscogsClient]
        Discogs client for metadata lookup (optional)

    Returns
    -------
    FileProcessingResult
        Result of processing this file
    """
    try:
        logger.info("Processing: %s", file_path.name)

        # Read existing tags
        tags = read_audio_tags(file_path)

        # Try to get artist/album from tags or path
        artist = tags.get('artist') or ''
        album = tags.get('album') or ''
        title = tags.get('title') or file_path.stem

        # If missing artist/album, try to detect from directory structure
        if not artist or not album:
            detected_artist, detected_album = detect_artist_album_from_path(
                file_path, source_dir)
            artist = artist or detected_artist or 'Unknown Artist'
            album = album or detected_album or 'Unknown Album'

        # Normalize names
        artist = normalize_spaces(artist)
        album = normalize_spaces(album)
        title = normalize_spaces(title)

        # Analyze BPM if requested and not already present in tags
        bpm_result = None
        existing_bpm = tags.get('bpm')

        if analyze_bpm and not dry_run:
            if existing_bpm:
                logger.info("BPM already exists in tags: %s", existing_bpm)
                bpm_result = {'bpm': existing_bpm}
            else:
                try:
                    bpm_result = analyze_and_tag_bpm(file_path, write_tag=True)
                    logger.info("BPM analysis: %s", bpm_result.get('bpm', 'N/A'))
                except (OSError, IOError, RuntimeError, ValueError) as e:
                    logger.warning(
                        "BPM analysis failed for %s: %s", file_path.name, e)

        # Build destination path: dest_root / artist / album / filename
        normalized_filename = normalize_filename(file_path.name)
        dest_dir = dest_root / artist / album
        dest_path = dest_dir / normalized_filename

        # Check if file already exists at destination
        if dest_path.exists() and dest_path != file_path:
            logger.warning("File already exists at destination: %s", dest_path)
            return FileProcessingResult(
                file_path=str(file_path),
                success=False,
                message="File already exists at destination",
                new_path=str(dest_path),
            )

        # Move file (or simulate if dry run)
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Only move if source and dest are different
            if file_path.resolve() != dest_path.resolve():
                shutil.move(str(file_path), str(dest_path))
                logger.info("Moved to: %s", dest_path)
            else:
                logger.info("File already at destination: %s", dest_path)
        else:
            logger.info("[DRY RUN] Would move to: %s", dest_path)

        return FileProcessingResult(
            file_path=str(file_path),
            success=True,
            message="Processed successfully",
            new_path=str(dest_path),
            metadata={
                'artist': artist,
                'album': album,
                'title': title,
                'bpm': bpm_result.get('bpm') if bpm_result else None,
            }
        )

    except (OSError, IOError, RuntimeError, ValueError, KeyError) as e:
        logger.error("Error processing %s: %s", file_path, str(e))
        return FileProcessingResult(
            file_path=str(file_path),
            success=False,
            message=f"Error: {str(e)}",
        )


def process_directory(
    source_dir: str,
    dest_root: str,
    db_path: Optional[str] = None,
    analyze_bpm: bool = True,
    dry_run: bool = False,
    discogs_client: Optional[DiscogsClient] = None,
) -> IngestReport:
    """
    Process all audio files in a directory through the ingest pipeline.

    This is the main entry point for the ingest workflow. It will:
    1. Find all audio files in source_dir
    2. Process each file (normalize, analyze BPM, move)
    3. Update the database with new locations
    4. Generate a report

    Parameters
    ----------
    source_dir : str
        Source directory to scan for audio files
    dest_root : str
        Root directory of organized music library
    db_path : Optional[str]
        Path to SQLite database file
    analyze_bpm : bool
        Whether to analyze and tag BPM (default: True)
    dry_run : bool
        If True, simulate without making actual changes (default: False)
    discogs_client : Optional[DiscogsClient]
        Discogs client for metadata lookup (optional)

    Returns
    -------
    IngestReport
        Detailed report of the ingest operation

    Example
    -------
    >>> from aft.ingest import process_directory
    >>> report = process_directory(
    ...     source_dir=r"D:\\Soulseek Downloads\\complete",
    ...     dest_root=r"D:\\Music Collection",
    ...     db_path="data/library.db",
    ...     dry_run=False
    ... )
    >>> print(report.summary())
    """
    source_path = Path(source_dir)
    dest_path = Path(dest_root)

    if not source_path.exists():
        logger.error("Source directory does not exist: %s", source_path)
        return IngestReport(
            source_dir=str(source_dir),
            dest_root=str(dest_root),
            dry_run=dry_run,
        )

    logger.info("Starting ingest from %s to %s", source_dir, dest_root)
    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Find all audio files
    audio_files = []
    for ext in AUDIO_EXTENSIONS:
        audio_files.extend(source_path.rglob(f'*{ext}'))

    # Also find cover art images
    image_files = []
    for ext in IMAGE_EXTENSIONS:
        image_files.extend(source_path.rglob(f'*{ext}'))

    report = IngestReport(
        source_dir=str(source_path),
        dest_root=str(dest_path),
        total_files=len(audio_files),
        dry_run=dry_run,
    )

    logger.info(
        "Found %d audio files and %d images", len(audio_files), len(image_files))

    # Process audio files
    for audio_file in audio_files:
        result = process_audio_file(
            audio_file,
            source_path,
            dest_path,
            analyze_bpm=analyze_bpm,
            dry_run=dry_run,
            discogs_client=discogs_client,
        )

        report.results.append(result)

        if result.success:
            report.processed += 1
        else:
            report.failed += 1

    # Move image files to corresponding album directories
    if not dry_run:
        for image_file in image_files:
            try:
                # Try to determine which album this belongs to
                # by looking at the directory structure
                relative = image_file.relative_to(source_path)
                parent_dir = relative.parent

                # Look for audio files in same directory to determine destination
                sibling_audio = list(image_file.parent.glob('*.[mM][pP]3'))
                sibling_audio.extend(
                    image_file.parent.glob('*.[fF][lL][aA][cC]'))

                if sibling_audio:
                    # Use first audio file to determine destination
                    first_audio = sibling_audio[0]

                    # Find corresponding result for this audio file
                    audio_result = next(
                        (r for r in report.results if Path(
                            r.file_path) == first_audio),
                        None
                    )

                    if audio_result and audio_result.new_path:
                        # Copy image to same directory as audio file
                        dest_image_dir = Path(audio_result.new_path).parent
                        dest_image_path = dest_image_dir / image_file.name

                        if not dest_image_path.exists():
                            shutil.copy2(str(image_file), str(dest_image_path))
                            logger.info("Copied cover art: %s", dest_image_path)

            except (OSError, IOError, ValueError) as e:
                logger.warning("Could not process image %s: %s", image_file, e)

    # Update database if not dry run
    if not dry_run and db_path:
        logger.info("Updating database...")
        session_factory = get_session_factory(
            db_path) if db_path else SessionLocal
        session = session_factory()

        try:
            for result in report.results:
                if result.success and result.new_path and result.metadata:
                    # Check if track already exists
                    track = session.query(Track).filter_by(
                        file_path=result.new_path).first()

                    if not track:
                        track = Track(
                            file_path=result.new_path,
                            title=result.metadata.get('title', ''),
                            artist=result.metadata.get('artist', ''),
                            album=result.metadata.get('album', ''),
                            bpm=result.metadata.get('bpm'),
                        )
                        session.add(track)

            session.commit()
            logger.info("Database updated successfully")

        except (OSError, IOError, RuntimeError, ValueError) as e:
            logger.error("Error updating database: %s", e)
            session.rollback()
        finally:
            session.close()

    logger.info(report.summary())
    return report
