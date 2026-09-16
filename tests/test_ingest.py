"""
Tests for the ingest pipeline's Discogs wiring.

Run with: pytest tests/test_ingest.py -v
"""
from unittest.mock import Mock, patch

from aft.ingest import process_audio_file


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
