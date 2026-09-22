"""
Tests for the ingest pipeline's Discogs wiring.

Run with: pytest tests/test_ingest.py -v
"""
from unittest.mock import Mock, patch

from aft.ingest import process_audio_file, process_directory


def test_process_audio_file_applies_discogs_metadata(tmp_path):
    """A supplied discogs_client must actually be used to tag the file.

    Regression test for the previously-dead discogs_client parameter:
    process_audio_file accepted it but never referenced it, so --use-discogs
    silently did nothing.
    """
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    audio_file = source_dir / "Artist - Album" / "track.mp3"
    audio_file.parent.mkdir()
    audio_file.touch()

    mock_discogs = Mock()
    mock_discogs.search_release.return_value = [{'id': 123}]
    mock_discogs.get_release_by_id.return_value = {
        'genres': ['House'],
        'styles': ['Deep House'],
        'labels': ['Test Label'],
        'catalog_numbers': ['TL001'],
    }

    with patch('aft.ingest.read_audio_tags', return_value={}), \
         patch('aft.ingest.write_audio_tags') as mock_write, \
         patch('aft.ingest.analyze_and_tag_bpm', return_value={'bpm': None}):
        process_audio_file(
            audio_file,
            source_dir,
            dest_dir,
            analyze_bpm=False,
            dry_run=False,
            discogs_client=mock_discogs,
        )

    mock_discogs.search_release.assert_called_once_with('Album', 'Artist')
    mock_discogs.get_release_by_id.assert_called_once_with(123)
    mock_write.assert_called_once_with(audio_file, {
        'genre': ['House'],
        'styles': ['Deep House'],
        'labels': ['Test Label'],
        'catalog_number': ['TL001'],
    })


def test_process_audio_file_skips_discogs_when_client_none(tmp_path):
    """No discogs_client supplied must mean no Discogs calls at all."""
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir()
    audio_file = source_dir / "Artist - Album" / "track.mp3"
    audio_file.parent.mkdir()
    audio_file.touch()

    with patch('aft.ingest.read_audio_tags', return_value={}), \
         patch('aft.ingest.write_audio_tags') as mock_write, \
         patch('aft.ingest.analyze_and_tag_bpm', return_value={'bpm': None}):
        process_audio_file(
            audio_file,
            source_dir,
            dest_dir,
            analyze_bpm=False,
            dry_run=False,
            discogs_client=None,
        )

    mock_write.assert_not_called()


def test_process_directory_moves_cover_art_and_removes_empty_source(tmp_path):
    """Cover art must move (not copy) alongside its audio file, and the
    now-empty release folder must be cleaned up afterward.

    Regression test: this previously used shutil.copy2 (leaving the
    original behind) and only matched mp3/flac siblings, and nothing
    ever removed the emptied-out source folder.
    """
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    release_dir = source_dir / "Artist - Album"
    release_dir.mkdir(parents=True)

    audio_file = release_dir / "track.m4a"  # deliberately not mp3/flac
    audio_file.touch()
    cover_file = release_dir / "cover.jpg"
    cover_file.write_bytes(b"fake-jpeg-bytes")

    with patch('aft.ingest.read_audio_tags', return_value={}), \
         patch('aft.ingest.write_audio_tags', return_value=True), \
         patch('aft.ingest.analyze_and_tag_bpm', return_value={'bpm': None}):
        report = process_directory(
            str(source_dir),
            str(dest_dir),
            db_path=None,
            analyze_bpm=False,
            dry_run=False,
        )

    assert report.processed == 1

    # Cover art moved to sit alongside the audio file at its destination
    moved_audio = list(dest_dir.rglob("track.m4a"))
    assert len(moved_audio) == 1
    moved_cover = moved_audio[0].parent / "cover.jpg"
    assert moved_cover.exists()

    # Source is gone entirely: image moved (not copied), folder emptied
    # out and removed
    assert not cover_file.exists()
    assert not release_dir.exists()
