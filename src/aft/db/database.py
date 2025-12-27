"""
Database session and engine setup for music library.
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import create_engine, or_, and_
from sqlalchemy.orm import sessionmaker, Session
from mutagen import File as MutagenFile  # type: ignore

from aft.db.models import Base, Artist, Release, Track
from aft.tags import read_audio_tags

logger = logging.getLogger(__name__)

# Audio file extensions to scan
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.mp4', '.ogg', '.wav'}


def get_database_url(db_path: Optional[str] = None) -> str:
    """
    Get database URL from environment or parameter.

    Parameters
    ----------
    db_path : Optional[str]
        Path to SQLite database file. If None, uses environment variable
        AFT_DB_URL or defaults to 'data/library.db'

    Returns
    -------
    str
        Database connection URL
    """
    if db_path:
        return f'sqlite:///{db_path}'

    # Default to SQLite for simplicity, can be changed to MySQL
    # To use MySQL, set the environment variable AFT_DB_URL to something like:
    # 'mysql+pymysql://user:password@localhost/music_library'
    db_url = os.getenv('AFT_DB_URL', 'sqlite:///data/library.db')
    return db_url


def get_engine(db_path: Optional[str] = None):
    """Get SQLAlchemy engine."""
    return create_engine(get_database_url(db_path), echo=False, future=True)


def get_session_factory(db_path: Optional[str] = None):
    """Get SQLAlchemy session factory."""
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


# Default engine and session factory
engine = get_engine()
SessionLocal = get_session_factory()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initialize database by creating all tables.

    Parameters
    ----------
    db_path : Optional[str]
        Path to SQLite database file. If None, uses default location.
    """
    eng = get_engine(db_path) if db_path else engine
    Base.metadata.create_all(bind=eng)
    logger.info("Database initialized at %s", db_path or 'default location')


def get_audio_file_metadata(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Extract metadata from an audio file.

    Parameters
    ----------
    file_path : Path
        Path to the audio file

    Returns
    -------
    Optional[Dict[str, Any]]
        Dictionary containing metadata, or None if error
    """
    try:
        # Get file stats
        stat = file_path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)

        # Read tags
        tags = read_audio_tags(file_path)

        # Get audio properties
        audio = MutagenFile(str(file_path))
        if audio is None:
            logger.warning("Could not load audio file: %s", file_path)
            return None

        info = audio.info
        duration = info.length if hasattr(info, 'length') else None
        bitrate = info.bitrate if hasattr(info, 'bitrate') else None
        sample_rate = info.sample_rate if hasattr(
            info, 'sample_rate') else None

        bpm_value = tags.get('bpm')
        bpm = None
        if bpm_value:
            try:
                bpm = float(bpm_value)
            except (ValueError, TypeError):
                logger.debug(
                    "Could not convert BPM value '%s' to float for %s", bpm_value, file_path)

        # Handle genre (can be list or string)
        genre = tags.get('genre', '')
        if isinstance(genre, list):
            genre = '; '.join(genre)

        # Handle publisher (can be list or string)
        publisher = tags.get('publisher', '')
        if isinstance(publisher, list):
            publisher = '; '.join(publisher)

        # Handle catalog number (can be list or string)
        catalog_number = tags.get('catalog_number', '')
        if isinstance(catalog_number, list):
            catalog_number = '; '.join(catalog_number)

        return {
            'file_path': str(file_path),
            'title': tags.get('title', file_path.stem),
            'artist': tags.get('artist', ''),
            'album_artist': tags.get('album_artist', ''),
            'album': tags.get('album', ''),
            'track_number': str(tags.get('track_number', '')),
            'disc_number': str(tags.get('disc_number', '')),
            'year': tags.get('year'),
            'genre': genre,
            'bpm': bpm,
            'key': tags.get('key', ''),
            'publisher': publisher,
            'catalog_number': catalog_number,
            'duration': duration,
            'bitrate': bitrate,
            'sample_rate': sample_rate,
            'last_modified': last_modified,
        }

    except Exception as e:
        logger.error("Error reading metadata from %s: %s", file_path, str(e))
        return None


def scan_library(base_path: str, db_path: Optional[str] = None) -> None:
    """
    Perform a full scan of the music library and update the database.

    This will scan all audio files in the base_path directory tree
    and add/update them in the database.

    Parameters
    ----------
    base_path : str
        Root directory of the music library to scan
    db_path : Optional[str]
        Path to SQLite database file. If None, uses default location.

    Example
    -------
    >>> from aft.db import scan_library
    >>> scan_library(r"D:\\Music Collection", "data/library.db")
    """
    base_path_obj = Path(base_path)

    if not base_path_obj.exists():
        logger.error("Base path does not exist: %s", base_path)
        return

    session_factory = get_session_factory(db_path) if db_path else SessionLocal
    session = session_factory()

    try:
        logger.info("Starting full library scan of %s", base_path)

        # Find all audio files
        audio_files = []
        for ext in AUDIO_EXTENSIONS:
            audio_files.extend(base_path_obj.rglob(f'*{ext}'))

        logger.info("Found %d audio files", len(audio_files))

        added_count = 0
        updated_count = 0

        for file_path in audio_files:
            try:
                # Get metadata
                metadata = get_audio_file_metadata(file_path)
                if metadata is None:
                    continue

                # Check if track exists in DB
                track = session.query(Track).filter_by(
                    file_path=str(file_path)).first()

                if track:
                    # Update existing track
                    for key, value in metadata.items():
                        setattr(track, key, value)
                    updated_count += 1
                else:
                    # Add new track
                    track = Track(**metadata)
                    session.add(track)
                    added_count += 1

                # Commit every 100 files
                if (added_count + updated_count) % 100 == 0:
                    session.commit()
                    logger.info(
                        "Progress: %d/%d files processed", added_count + updated_count, len(audio_files))

            except Exception as e:
                logger.error("Error processing %s: %s", file_path, str(e))
                continue

        session.commit()
        logger.info(
            "Scan complete. Added: %d, Updated: %d", added_count, updated_count)

    except Exception as e:
        logger.error("Error during library scan: %s", str(e))
        session.rollback()
    finally:
        session.close()


def incremental_update(base_path: str, db_path: Optional[str] = None) -> List[str]:
    """
    Detect new or modified files in the library and update database.

    This is faster than a full scan as it only checks files that are
    new or have been modified since last scan.

    Parameters
    ----------
    base_path : str
        Root directory of the music library
    db_path : Optional[str]
        Path to SQLite database file. If None, uses default location.

    Returns
    -------
    List[str]
        List of file paths that were added or updated

    Example
    -------
    >>> from aft.db import incremental_update
    >>> updated_files = incremental_update(r"D:\\Music Collection")
    >>> print(f"Updated {len(updated_files)} files")
    """
    base_path_obj = Path(base_path)

    if not base_path_obj.exists():
        logger.error("Base path does not exist: %s", base_path)
        return []

    session_factory = get_session_factory(db_path) if db_path else SessionLocal
    session = session_factory()

    updated_files = []

    try:
        logger.info("Starting incremental update of %s", base_path)

        # Get all existing tracks from DB
        existing_tracks = {
            track.file_path: track.last_modified
            for track in session.query(Track).all()
        }

        # Find all audio files
        audio_files = []
        for ext in AUDIO_EXTENSIONS:
            audio_files.extend(base_path_obj.rglob(f'*{ext}'))

        added_count = 0
        updated_count = 0

        for file_path in audio_files:
            try:
                file_path_str = str(file_path)
                stat = file_path.stat()
                last_modified = datetime.fromtimestamp(stat.st_mtime)

                # Check if file is new or modified
                if file_path_str not in existing_tracks:
                    # New file
                    metadata = get_audio_file_metadata(file_path)
                    if metadata:
                        track = Track(**metadata)
                        session.add(track)
                        updated_files.append(file_path_str)
                        added_count += 1

                elif existing_tracks[file_path_str] < last_modified:  # type: ignore
                    # Modified file
                    metadata = get_audio_file_metadata(file_path)
                    if metadata:
                        track = session.query(Track).filter_by(
                            file_path=file_path_str).first()
                        for key, value in metadata.items():
                            setattr(track, key, value)
                        updated_files.append(file_path_str)
                        updated_count += 1

                # Commit every 100 files
                if (added_count + updated_count) % 100 == 0:
                    session.commit()

            except Exception as e:
                logger.error("Error processing %s: %s", file_path, str(e))
                continue

        session.commit()
        logger.info(
            "Incremental update complete. Added: %d, Updated: %d", added_count, updated_count)

    except Exception as e:
        logger.error("Error during incremental update: %s", str(e))
        session.rollback()
    finally:
        session.close()

    return updated_files


def query(
    session: Optional[Session] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    title: Optional[str] = None,
    genre: Optional[str] = None,
    bpm_range: Optional[tuple[float, float]] = None,
    year_range: Optional[tuple[int, int]] = None,
    text_search: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: Optional[str] = None,
) -> List[Track]:
    """
    Query the music library database with various filters.

    Parameters
    ----------
    session : Optional[Session]
        Existing database session. If None, creates a new one.
    artist : Optional[str]
        Filter by artist name (case-insensitive partial match)
    album : Optional[str]
        Filter by album name (case-insensitive partial match)
    title : Optional[str]
        Filter by track title (case-insensitive partial match)
    genre : Optional[str]
        Filter by genre (case-insensitive partial match)
    bpm_range : Optional[tuple[float, float]]
        Filter by BPM range, e.g., (120, 140)
    year_range : Optional[tuple[int, int]]
        Filter by year range, e.g., (2000, 2010)
    text_search : Optional[str]
        Search across artist, album, and title fields
    limit : Optional[int]
        Maximum number of results to return
    db_path : Optional[str]
        Path to SQLite database file. If None, uses default location.

    Returns
    -------
    List[Track]
        List of matching Track objects

    Example
    -------
    >>> from aft.db import query
    >>> # Find all tracks by an artist
    >>> tracks = query(artist="The Beatles")
    >>> 
    >>> # Find tracks in a specific BPM range
    >>> tracks = query(bpm_range=(120, 130))
    >>> 
    >>> # Complex query
    >>> tracks = query(
    ...     artist="Daft Punk",
    ...     bpm_range=(110, 130),
    ...     year_range=(2000, 2020),
    ...     limit=50
    ... )
    """
    # Create session if not provided
    close_session = False
    if session is None:
        session_factory = get_session_factory(
            db_path) if db_path else SessionLocal
        session = session_factory()
        close_session = True

    try:
        # Build query
        q = session.query(Track)

        # Apply filters
        if artist:
            q = q.filter(Track.artist.ilike(f'%{artist}%'))

        if album:
            q = q.filter(Track.album.ilike(f'%{album}%'))

        if title:
            q = q.filter(Track.title.ilike(f'%{title}%'))

        if genre:
            q = q.filter(Track.genre.ilike(f'%{genre}%'))

        if bpm_range:
            min_bpm, max_bpm = bpm_range
            q = q.filter(and_(Track.bpm >= min_bpm, Track.bpm <= max_bpm))

        if year_range:
            min_year, max_year = year_range
            q = q.filter(and_(Track.year >= min_year, Track.year <= max_year))

        if text_search:
            search_filter = or_(
                Track.artist.ilike(f'%{text_search}%'),
                Track.album.ilike(f'%{text_search}%'),
                Track.title.ilike(f'%{text_search}%')
            )
            q = q.filter(search_filter)

        # Apply limit
        if limit:
            q = q.limit(limit)

        results = q.all()
        logger.info("Query returned %d results", len(results))
        return results

    except Exception as e:
        logger.error("Error during query: %s", str(e))
        return []
    finally:
        if close_session:
            session.close()
