"""
Tests for database module.

Run with: pytest tests/test_database.py -v
"""
import pytest
from unittest.mock import patch
from aft.db.database import (
    init_db, scan_library, incremental_update, query,
    update_track_path, find_orphaned_tracks, remove_orphaned_tracks,
)
from aft.db.models import Track


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_library.db")
    init_db(db_path)
    return db_path


def test_init_db_creates_tables(temp_db):
    """Test that init_db creates database tables."""
    from sqlalchemy import inspect
    from aft.db.database import get_engine
    
    engine = get_engine(temp_db)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    assert 'tracks' in tables
    assert 'artists' in tables
    assert 'releases' in tables


def test_query_by_artist(temp_db):
    """Test querying tracks by artist."""
    from aft.db.database import get_session_factory
    
    # Add test data
    session_factory = get_session_factory(temp_db)
    session = session_factory()
    
    track = Track(
        title="Test Track",
        artist="Test Artist",
        album="Test Album",
        file_path="/test/path.mp3",
        bpm=128.0
    )
    session.add(track)
    session.commit()
    session.close()
    
    # Query
    results = query(artist="Test Artist", db_path=temp_db)
    
    assert len(results) == 1
    assert results[0].artist == "Test Artist"


def test_query_by_bpm_range(temp_db):
    """Test querying tracks by BPM range."""
    from aft.db.database import get_session_factory
    
    # Add test data with different BPMs
    session_factory = get_session_factory(temp_db)
    session = session_factory()
    
    tracks_data = [
        ("Track 1", 120.0),
        ("Track 2", 128.0),
        ("Track 3", 140.0),
        ("Track 4", 150.0),
    ]
    
    for title, bpm in tracks_data:
        track = Track(
            title=title,
            artist="Test Artist",
            file_path=f"/test/{title}.mp3",
            bpm=bpm
        )
        session.add(track)
    
    session.commit()
    session.close()
    
    # Query for BPM between 125 and 145
    results = query(bpm_range=(125, 145), db_path=temp_db)
    
    assert len(results) == 2
    assert all(125 <= track.bpm <= 145 for track in results)


def test_query_text_search(temp_db):
    """Test text search across multiple fields."""
    from aft.db.database import get_session_factory
    
    session_factory = get_session_factory(temp_db)
    session = session_factory()
    
    track1 = Track(
        title="Searching for Something",
        artist="Test Artist",
        file_path="/test/track1.mp3"
    )
    track2 = Track(
        title="Another Track",
        artist="Searching Artist",
        file_path="/test/track2.mp3"
    )
    track3 = Track(
        title="Unrelated Track",
        artist="Other Artist",
        file_path="/test/track3.mp3"
    )
    
    session.add_all([track1, track2, track3])
    session.commit()
    session.close()
    
    # Search for "Searching"
    results = query(text_search="Searching", db_path=temp_db)
    
    assert len(results) == 2


def test_scan_library_with_mock_files(temp_db, tmp_path):
    """Test library scanning with mock files."""
    # Create mock audio files
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    
    (music_dir / "track1.mp3").touch()
    (music_dir / "track2.mp3").touch()
    
    with patch('aft.db.database.get_audio_file_metadata') as mock_get_metadata:
        mock_get_metadata.side_effect = [
            {
                'file_path': str(music_dir / 'track1.mp3'),
                'title': 'Track 1',
                'artist': 'Artist 1',
                'album': 'Album 1',
                'bpm': 128.0,
                'duration': 240.0,
                'bitrate': 320000,
                'sample_rate': 44100,
                'tags_json': {},
                'last_modified': None,
            },
            {
                'file_path': str(music_dir / 'track2.mp3'),
                'title': 'Track 2',
                'artist': 'Artist 1',
                'album': 'Album 1',
                'bpm': 130.0,
                'duration': 180.0,
                'bitrate': 320000,
                'sample_rate': 44100,
                'tags_json': {},
                'last_modified': None,
            }
        ]
        
        scan_library(str(music_dir), temp_db)
        
        # Verify tracks were added
        results = query(db_path=temp_db)
        assert len(results) == 2


def test_incremental_update_detects_new_files(temp_db, tmp_path):
    """Test that incremental update detects new files."""
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    
    # Initial scan with one file
    (music_dir / "track1.mp3").touch()
    
    with patch('aft.db.database.get_audio_file_metadata') as mock_get_metadata:
        mock_get_metadata.return_value = {
            'file_path': str(music_dir / 'track1.mp3'),
            'title': 'Track 1',
            'artist': 'Artist 1',
            'album': 'Album 1',
            'file_path': str(music_dir / 'track1.mp3'),
            'bpm': None,
            'duration': None,
            'bitrate': None,
            'sample_rate': None,
            'tags_json': {},
            'last_modified': None,
        }
        
        scan_library(str(music_dir), temp_db)
    
    # Add new file
    (music_dir / "track2.mp3").touch()
    
    with patch('aft.db.database.get_audio_file_metadata') as mock_get_metadata:
        mock_get_metadata.return_value = {
            'file_path': str(music_dir / 'track2.mp3'),
            'title': 'Track 2',
            'artist': 'Artist 1',
            'album': 'Album 1',
            'bpm': None,
            'duration': None,
            'bitrate': None,
            'sample_rate': None,
            'tags_json': {},
            'last_modified': None,
        }
        
        updated = incremental_update(str(music_dir), temp_db)

        assert len(updated) == 1
        assert str(music_dir / 'track2.mp3') in updated[0]


def test_update_track_path(temp_db):
    """Renaming a file should be reflected in its Track row."""
    from aft.db.database import get_session_factory

    session_factory = get_session_factory(temp_db)
    session = session_factory()
    session.add(Track(title="T", artist="A", album="Al", file_path="/old/path.mp3"))
    session.commit()
    session.close()

    assert update_track_path("/old/path.mp3", "/new/path.mp3", db_path=temp_db) is True

    results = query(db_path=temp_db)
    assert results[0].file_path == "/new/path.mp3"


def test_update_track_path_missing_row(temp_db):
    """Updating a path with no matching row should report failure, not raise."""
    assert update_track_path("/nope.mp3", "/new/path.mp3", db_path=temp_db) is False


def test_find_and_remove_orphaned_tracks(temp_db, tmp_path):
    """Rows whose file no longer exists should be found and removable;
    rows whose file still exists must be left alone."""
    from aft.db.database import get_session_factory

    real_file = tmp_path / "real.mp3"
    real_file.touch()

    session_factory = get_session_factory(temp_db)
    session = session_factory()
    session.add(Track(title="Real", artist="A", album="Al", file_path=str(real_file)))
    session.add(Track(title="Gone", artist="A", album="Al", file_path=str(tmp_path / "gone.mp3")))
    session.commit()
    session.close()

    orphans = find_orphaned_tracks(db_path=temp_db)
    assert len(orphans) == 1
    assert orphans[0].title == "Gone"

    removed = remove_orphaned_tracks(db_path=temp_db)
    assert removed == 1

    remaining = query(db_path=temp_db)
    assert len(remaining) == 1
    assert remaining[0].title == "Real"
