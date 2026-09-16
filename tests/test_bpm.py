"""
Tests for BPM detection module.

Run with: pytest tests/test_bpm.py -v
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch
from aft.bpm import (
    analyze_bpm,
    write_bpm_tag,
    analyze_and_tag_bpm,
    _correct_octave_error,
)


@pytest.fixture
def mock_audio_file(tmp_path):
    """Create a temporary mock audio file."""
    audio_file = tmp_path / "test_track.mp3"
    audio_file.touch()
    return audio_file


def test_analyze_bpm_structure():
    """Test that analyze_bpm returns correct structure."""
    with patch('aft.bpm.librosa.load') as mock_load, \
         patch('aft.bpm.librosa.onset.onset_strength') as mock_onset, \
         patch('aft.bpm.librosa.beat.beat_track') as mock_beat:
        
        # Mock librosa functions
        mock_load.return_value = (np.array([0.1] * 25000), 22050)
        mock_onset.return_value = np.array([0.5] * 100)
        mock_beat.return_value = (128.0, np.array([10, 20, 30, 40]))

        result = analyze_bpm("dummy.mp3")

        # Check structure
        assert 'file_path' in result
        assert 'bpm' in result
        assert 'confidence' in result
        assert 'duration' in result
        assert 'samples' in result
        # bpm/confidence being non-None confirms no exception was swallowed
        # partway through analysis (the mock data must stay internally
        # consistent with the real librosa call chain for this to hold).
        assert result['bpm'] is not None
        assert result['confidence'] is not None


def test_analyze_bpm_returns_float_bpm():
    """Test that BPM is returned as float."""
    with patch('aft.bpm.librosa.load') as mock_load, \
         patch('aft.bpm.librosa.onset.onset_strength') as mock_onset, \
         patch('aft.bpm.librosa.beat.beat_track') as mock_beat:
        
        mock_load.return_value = (np.array([0.1] * 25000), 22050)
        mock_onset.return_value = np.array([0.5] * 100)
        mock_beat.return_value = (128.5, np.array([10, 20, 30, 40]))

        result = analyze_bpm("dummy.mp3")

        assert isinstance(result['bpm'], float)


def test_analyze_bpm_error_handling():
    """Test that errors are handled gracefully."""
    with patch('aft.bpm.librosa.load', side_effect=Exception("File not found")):
        result = analyze_bpm("nonexistent.mp3")
        
        assert result['bpm'] is None
        assert result['confidence'] == 0.0


def test_write_bpm_tag_mp3(mock_audio_file):
    """Test writing BPM tag to MP3 file."""
    with patch('aft.bpm.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio
        
        success = write_bpm_tag(mock_audio_file, 128.5)
        
        assert success is True
        assert 'TBPM' in mock_audio.tags


def test_write_bpm_tag_rounds_bpm():
    """Test that BPM is rounded to integer for tag writing."""
    with patch('aft.bpm.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_audio.suffix = '.mp3'
        mock_file.return_value = mock_audio
        
        write_bpm_tag("test.mp3", 128.7)
        
        # Check that rounded value (129) was used
        assert mock_audio.tags['TBPM'].text[0] == '129'


def test_analyze_and_tag_bpm_integration():
    """Test complete analyze and tag workflow."""
    with patch('aft.bpm.analyze_bpm') as mock_analyze, \
         patch('aft.bpm.write_bpm_tag') as mock_write:
        
        mock_analyze.return_value = {
            'file_path': 'test.mp3',
            'bpm': 128.0,
            'confidence': 0.95,
            'duration': 240.0,
            'samples': 5292000
        }
        mock_write.return_value = True
        
        result = analyze_and_tag_bpm("test.mp3", write_tag=True)
        
        assert result['bpm'] == 128.0
        mock_write.assert_called_once_with("test.mp3", 128.0)


def test_correct_octave_error_fixes_half_tempo():
    """A raw estimate at half the true tempo should be corrected back up."""
    sr = 22050
    hop_length = 512
    frame_rate = sr / hop_length
    true_bpm = 170.0
    period_s = 60.0 / true_bpm

    n_frames = int(20.0 * frame_rate)
    onset_env = np.zeros(n_frames)
    t = 0.0
    while t < 20.0:
        frame = int(round(t * frame_rate))
        if frame < n_frames:
            onset_env[frame] = 1.0
        t += period_s

    wrong_tempo = true_bpm / 2
    corrected = _correct_octave_error(wrong_tempo, onset_env, sr, hop_length, 60.0, 200.0)

    assert abs(corrected - true_bpm) < 2.0


def test_correct_octave_error_fixes_double_tempo():
    """A raw estimate at double the true tempo should be corrected back down."""
    sr = 22050
    hop_length = 512
    frame_rate = sr / hop_length
    true_bpm = 170.0
    period_s = 60.0 / true_bpm

    n_frames = int(20.0 * frame_rate)
    onset_env = np.zeros(n_frames)
    t = 0.0
    while t < 20.0:
        frame = int(round(t * frame_rate))
        if frame < n_frames:
            onset_env[frame] = 1.0
        t += period_s

    wrong_tempo = true_bpm * 2
    corrected = _correct_octave_error(wrong_tempo, onset_env, sr, hop_length, 60.0, 400.0)

    assert abs(corrected - true_bpm) < 2.0


def test_write_bpm_tag_rejects_implausible_value():
    """A bounds check must reject garbage BPM values before writing."""
    with patch('aft.bpm.File') as mock_file:
        mock_audio = Mock()
        mock_audio.tags = {}
        mock_file.return_value = mock_audio

        success = write_bpm_tag("test.mp3", 5.0)

        assert success is False
        mock_file.assert_not_called()


def test_analyze_and_tag_bpm_skip_write():
    """Test that writing can be skipped."""
    with patch('aft.bpm.analyze_bpm') as mock_analyze, \
         patch('aft.bpm.write_bpm_tag') as mock_write:
        
        mock_analyze.return_value = {
            'file_path': 'test.mp3',
            'bpm': 128.0,
            'confidence': 0.95,
            'duration': 240.0,
            'samples': 5292000
        }
        
        result = analyze_and_tag_bpm("test.mp3", write_tag=False)
        
        assert result['bpm'] == 128.0
        mock_write.assert_not_called()
