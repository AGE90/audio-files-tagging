"""
Tests for tags module.

Run with: pytest tests/test_tags.py -v
"""
from unittest.mock import Mock, patch, MagicMock
from aft.tags import AudioTags


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
        frames = {
            'TIT2': Mock(text=['Test Title']),
            'TPE1': Mock(text=['Test Artist']),
            'TALB': Mock(text=['Test Album']),
        }
        mock_audio = Mock()
        # Real ID3 tags support both dict-style .get() and .getall() (for
        # TXXX/COMM, which _read_mp3_tags always queries) - a plain dict
        # only supports .get(), so it fails on the read of every file.
        mock_audio.tags = MagicMock()
        mock_audio.tags.get.side_effect = lambda k, default=None: frames.get(k, default)
        mock_audio.tags.getall.return_value = []
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


def test_audio_tags_write_mp4_multi_genre():
    """MP4 genre write must keep all genres+styles, not just the first."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = MagicMock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio

        tags = AudioTags('test.m4a')
        tags.write_tags({
            'genre': ['House', 'Techno'],
            'styles': ['Deep House', 'Minimal'],
        })

        assert mock_audio.tags['\xa9gen'] == ['House', 'Techno', 'Deep House', 'Minimal']


def test_audio_tags_read_mp4_multi_genre():
    """MP4 genre read must return all genres, not just the first."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {
            '\xa9gen': ['House', 'Techno'],
        }
        mock_file.return_value = mock_audio

        tags = AudioTags('test.m4a')
        metadata = tags.read_tags()

        assert metadata['genre'] == 'House; Techno'


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


def test_audio_tags_read_mp4_bpm_absent_is_empty_string():
    """An m4a with no tmpo atom must read bpm as '', not the stringified
    default 0 - ingest.py's `if existing_bpm:` check treats a truthy '0'
    as an already-tagged BPM and silently skips real analysis."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio

        tags = AudioTags('test.m4a')
        metadata = tags.read_tags()

        assert metadata['bpm'] == ''


def test_audio_tags_write_mp4_labels_and_catalog_number():
    """MP4 write must persist labels/catalog_number via freeform atoms -
    previously silently dropped (no MP4 handling existed at all)."""
    with patch('aft.tags.File') as mock_file:
        mock_audio = MagicMock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio

        tags = AudioTags('test.m4a')
        tags.write_tags({
            'labels': ['Test Label'],
            'catalog_number': ['TL-001'],
        })

        assert bytes(mock_audio.tags['----:com.apple.iTunes:LABEL'][0]) == b'Test Label'
        assert bytes(mock_audio.tags['----:com.apple.iTunes:CATALOGNUMBER'][0]) == b'TL-001'


def test_audio_tags_read_mp4_freeform_publisher():
    """MP4 freeform (----) atoms must decode to plain strings on read."""
    from mutagen.mp4 import MP4FreeForm
    with patch('aft.tags.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {
            '----:com.apple.iTunes:LABEL': [MP4FreeForm(b'Test Label')],
        }
        mock_file.return_value = mock_audio

        tags = AudioTags('test.m4a')
        metadata = tags.read_tags()

        assert metadata['publisher'] == 'Test Label'
