"""
Tests for musical key detection module.

Run with: pytest tests/test_key.py -v
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch
from aft.key import (
    analyze_key,
    write_key_tag,
    analyze_and_tag_key,
    MAJOR_PROFILE,
)


@pytest.fixture
def mock_audio_file(tmp_path):
    """Create a temporary mock audio file."""
    audio_file = tmp_path / "test_track.mp3"
    audio_file.touch()
    return audio_file


def test_analyze_key_identifies_c_major():
    """A chroma vector matching the C major profile exactly should be
    identified as C major with high confidence."""
    with patch('aft.key.librosa.load') as mock_load, \
         patch('aft.key.librosa.feature.chroma_cqt') as mock_chroma:

        mock_load.return_value = (np.array([0.1] * 25000), 22050)
        # Broadcast the C major profile across frames so the mean chroma
        # is exactly the unrotated major profile
        mock_chroma.return_value = np.tile(MAJOR_PROFILE.reshape(12, 1), (1, 10))

        result = analyze_key("dummy.mp3")

        assert result['key'] == 'C major'
        assert result['camelot'] == '8B'
        assert result['confidence'] > 0.9


def test_analyze_key_structure():
    """analyze_key should always return the documented keys."""
    with patch('aft.key.librosa.load') as mock_load, \
         patch('aft.key.librosa.feature.chroma_cqt') as mock_chroma:

        mock_load.return_value = (np.array([0.1] * 25000), 22050)
        mock_chroma.return_value = np.tile(MAJOR_PROFILE.reshape(12, 1), (1, 10))

        result = analyze_key("dummy.mp3")

        for field in ('file_path', 'key', 'camelot', 'confidence', 'duration', 'samples'):
            assert field in result


def test_analyze_key_error_handling():
    """Errors during analysis must not propagate - callers batch over
    many files and a single bad one shouldn't abort the run."""
    with patch('aft.key.librosa.load', side_effect=Exception("File not found")):
        result = analyze_key("nonexistent.mp3")

        assert result['key'] is None
        assert result['confidence'] == 0.0


def test_write_key_tag_mp3(mock_audio_file):
    """Test writing key tag to MP3 file."""
    with patch('aft.key.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio

        success = write_key_tag(mock_audio_file, "C major")

        assert success is True
        assert 'TKEY' in mock_audio.tags
        assert mock_audio.tags['TKEY'].text[0] == 'C major'


def test_write_key_tag_rejects_empty_key(mock_audio_file):
    """Refuse to write an empty/falsy key rather than clobbering the tag."""
    success = write_key_tag(mock_audio_file, "")
    assert success is False


def test_analyze_and_tag_key_integration():
    """Test complete analyze and tag workflow."""
    with patch('aft.key.analyze_key') as mock_analyze, \
         patch('aft.key.write_key_tag') as mock_write:

        mock_analyze.return_value = {
            'file_path': 'test.mp3',
            'key': 'A minor',
            'camelot': '8A',
            'confidence': 0.85,
            'duration': 240.0,
            'samples': 5292000,
        }
        mock_write.return_value = True

        result = analyze_and_tag_key("test.mp3", write_tag=True)

        assert result['key'] == 'A minor'
        mock_write.assert_called_once_with("test.mp3", 'A minor')
