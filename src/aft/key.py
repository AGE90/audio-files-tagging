"""
Musical key detection and tagging module.

Uses librosa chroma features correlated against the Krumhansl-Schmuckler
key profiles to estimate a track's musical key, mirroring aft.bpm's
analyze/write/analyze_and_tag structure.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from mutagen import File, MutagenError  # type: ignore
from mutagen.flac import FLAC
from mutagen.id3 import TKEY  # type: ignore
from mutagen.mp4 import MP4, MP4FreeForm

logger = logging.getLogger(__name__)

PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Krumhansl-Schmuckler key profiles (relative pitch-class weights)
MAJOR_PROFILE = np.array([
    6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88,
])
MINOR_PROFILE = np.array([
    6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17,
])

# Standard Camelot wheel mapping, keyed by (pitch class index, mode)
_CAMELOT = {
    ('C', 'major'): '8B', ('A', 'minor'): '8A',
    ('G', 'major'): '9B', ('E', 'minor'): '9A',
    ('D', 'major'): '10B', ('B', 'minor'): '10A',
    ('A', 'major'): '11B', ('F#', 'minor'): '11A',
    ('E', 'major'): '12B', ('C#', 'minor'): '12A',
    ('B', 'major'): '1B', ('G#', 'minor'): '1A',
    ('F#', 'major'): '2B', ('D#', 'minor'): '2A',
    ('C#', 'major'): '3B', ('A#', 'minor'): '3A',
    ('G#', 'major'): '4B', ('F', 'minor'): '4A',
    ('D#', 'major'): '5B', ('C', 'minor'): '5A',
    ('A#', 'major'): '6B', ('G', 'minor'): '6A',
    ('F', 'major'): '7B', ('D', 'minor'): '7A',
}


@dataclass
class KeyAnalysisConfig:
    """
    Configuration for key analysis.

    Attributes
    ----------
    sr : Optional[int]
        Sample rate for audio loading (default: None, uses original sample rate).
    hop_length : int
        Number of samples between successive chroma frames (default: 512).
    """
    sr: int | None = None
    hop_length: int = 512


def _correlate_profile(
    chroma_mean: np.ndarray, profile: np.ndarray, shift: int
) -> float:
    """Pearson correlation between a chroma vector and a profile rotated by `shift`."""
    rotated = np.roll(profile, shift)
    if np.std(chroma_mean) == 0 or np.std(rotated) == 0:
        return 0.0
    return float(np.corrcoef(chroma_mean, rotated)[0, 1])


def analyze_key(
    file_path: str | Path,
    config: KeyAnalysisConfig | None = None,
) -> dict[str, str | float | int | None]:
    """
    Estimate the musical key of an audio file using librosa chroma features.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file to analyze.
    config : Optional[KeyAnalysisConfig]
        Configuration object for analysis parameters.

    Returns
    -------
    Dict[str, Union[str, float, int, None]]
        Dictionary containing:
        - file_path: str
        - key: str - e.g. "C major" / "A minor"
        - camelot: str - Camelot wheel notation, e.g. "8B"
        - confidence: float - correlation-based confidence score (0-1)
        - duration: float
        - samples: int

    Example
    -------
    >>> result = analyze_key("track.mp3")
    >>> print(f"Key: {result['key']} ({result['camelot']})")
    """
    if config is None:
        config = KeyAnalysisConfig()
    file_path = Path(file_path)

    result: dict[str, str | float | int | None] = {
        'file_path': str(file_path),
        'duration': None,
        'samples': None,
        'key': None,
        'camelot': None,
        'confidence': None,
    }

    try:
        y, sample_rate = librosa.load(str(file_path), sr=config.sr)
        result['duration'] = float(librosa.get_duration(y=y, sr=sample_rate))
        result['samples'] = len(y)

        chroma = librosa.feature.chroma_cqt(
            y=y, sr=sample_rate, hop_length=config.hop_length)
        chroma_mean = chroma.mean(axis=1)

        best_score = -2.0
        best_pitch_idx = 0
        best_mode = 'major'
        for pitch_idx in range(12):
            major_score = _correlate_profile(chroma_mean, MAJOR_PROFILE, pitch_idx)
            minor_score = _correlate_profile(chroma_mean, MINOR_PROFILE, pitch_idx)
            if major_score > best_score:
                best_score, best_pitch_idx, best_mode = major_score, pitch_idx, 'major'
            if minor_score > best_score:
                best_score, best_pitch_idx, best_mode = minor_score, pitch_idx, 'minor'

        pitch_name = PITCH_CLASSES[best_pitch_idx]
        result['key'] = f"{pitch_name} {best_mode}"
        result['camelot'] = _CAMELOT.get((pitch_name, best_mode))
        # Correlation is in [-1, 1]; clip and rescale to a 0-1 confidence
        result['confidence'] = float(max(0.0, min(1.0, (best_score + 1) / 2)))

        logger.info(
            "Key analysis complete for %s: %s (%s, confidence: %.2f)",
            file_path.name, result['key'], result['camelot'], result['confidence']
        )

    except Exception as e:
        # Mirrors aft.bpm.analyze_bpm: a single unreadable/corrupt file must
        # not crash a batch run over the rest of the library
        logger.error("Error analyzing key for %s: %s", file_path, str(e))
        result['key'] = None
        result['confidence'] = 0.0

    return result


def write_key_tag(file_path: str | Path, key: str) -> bool:
    """
    Write a musical key value to audio file tags.

    Supports MP3 (ID3v2 TKEY), FLAC (INITIALKEY), M4A/MP4 (freeform atom),
    and OGG Vorbis (INITIALKEY) formats.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file.
    key : str
        Key value to write, e.g. "C major" or a Camelot code like "8B".

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    file_path = Path(file_path)

    if not key:
        logger.warning("Refusing to write an empty key to %s", file_path)
        return False

    try:
        audio = File(str(file_path))

        if audio is None:
            logger.error("Could not load file: %s", file_path)
            return False

        if file_path.suffix.lower() == '.mp3':
            if audio.tags is None:
                audio.add_tags()
            audio.tags['TKEY'] = TKEY(encoding=3, text=key)

        elif isinstance(audio, FLAC):
            audio['INITIALKEY'] = key

        elif isinstance(audio, MP4):
            audio['----:com.apple.iTunes:initialkey'] = [
                MP4FreeForm(key.encode('utf-8'))
            ]

        elif hasattr(audio, 'tags') and audio.tags is not None:
            audio['INITIALKEY'] = key

        else:
            logger.warning("Unsupported audio format for %s", file_path)
            return False

        audio.save()
        logger.info("Successfully wrote key %s to %s", key, file_path.name)
        return True

    except (MutagenError, FileNotFoundError, OSError, ValueError, TypeError) as e:
        logger.error("Error writing key tag to %s: %s", file_path, str(e))
        return False


def analyze_and_tag_key(
    file_path: str | Path,
    write_tag: bool = True,
) -> dict[str, str | float | int | None]:
    """
    Analyze the musical key of an audio file and optionally write it to tags.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file to analyze.
    write_tag : bool, optional
        If True, write the detected key to the file's tags (default: True).

    Returns
    -------
    Dict[str, Union[str, float, int, None]]
        Same shape as analyze_key.

    Example
    -------
    >>> from aft.key import analyze_and_tag_key
    >>> result = analyze_and_tag_key("track.mp3", write_tag=True)
    """
    result = analyze_key(file_path)

    if write_tag and result['key']:
        success = write_key_tag(file_path, str(result['key']))
        if not success:
            logger.warning("Key detected but could not write tag for %s", file_path)

    return result
