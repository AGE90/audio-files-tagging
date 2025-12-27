"""
Tests for tags module.

Run with: pytest tests/test_tags.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from aft.tags import AudioTags, normalize_filename


def test_normalize_filename():
    """Test filename normalization."""
    from aft.ingest import normalize_filename
    
    # Test illegal characters
    assert normalize_filename('track<1>.mp3') == 'track1.mp3'
    assert normalize_filename('artist|album.mp3') == 'artistalbum.mp3'
    
    # Test multiple spaces
    assert normalize_filename('track   name.mp3') == 'track name.mp3'
    
    # Test multiple dots
    assert normalize_filename('track..name.mp3') == 'track.name.mp3'


def test_audio_tags_read_mp3():
    """Test reading tags from MP3 file."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {
            'TIT2': Mock(text=['Test Title']),
            'TPE1': Mock(text=['Test Artist']),
            'TALB': Mock(text=['Test Album']),
        }
        mock_file.return_value = mock_audio
        
        tags = AudioTags('test.mp3')
        metadata = tags.read_tags()
        
        assert metadata['title'] == 'Test Title'
        assert metadata['artist'] == 'Test Artist'
        assert metadata['album'] == 'Test Album'


def test_audio_tags_write_mp3():
    """Test writing tags to MP3 file."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = MagicMock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio
        
        tags = AudioTags('test.mp3')
        success = tags.write_tags({
            'artist': 'New Artist',
            'album': 'New Album',
            'bpm': 128
        })
        
        assert success is True
        assert 'TPE1' in mock_audio.tags
        assert 'TALB' in mock_audio.tags
        assert 'TBPM' in mock_audio.tags


def test_audio_tags_merge_genre_and_styles():
    """Test that genre and styles are merged."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = MagicMock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio
        
        tags = AudioTags('test.mp3')
        tags.write_tags({
            'genre': ['Electronic'],
            'styles': ['House', 'Techno']
        })
        
        # Check that TCON frame contains all genres/styles
        assert 'TCON' in mock_audio.tags


def test_audio_tags_handles_missing_file():
    """Test handling of missing audio file."""
    with patch('aft.tags.File', return_value=None):
        tags = AudioTags('nonexistent.mp3')
        metadata = tags.read_tags()
        
        assert metadata == {}


def test_audio_tags_flac_support():
    """Test FLAC file support."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {
            'TITLE': ['Test Title'],
            'ARTIST': ['Test Artist'],
            'BPM': ['128']
        }
        mock_file.return_value = mock_audio
        
        tags = AudioTags('test.flac')
        metadata = tags.read_tags()
        
        assert metadata['title'] == 'Test Title'
        assert metadata['artist'] == 'Test Artist'
        assert metadata['bpm'] == '128'
