"""
BPM detection and tagging module.

Uses librosa for robust BPM detection across various tempos.
Writes BPM values to audio file tags using mutagen.
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Union, Callable

import librosa
import matplotlib.pyplot as plt
import numpy as np
from mutagen import File, MutagenError # type: ignore
from mutagen.flac import FLAC
from mutagen.id3 import TBPM # type: ignore
from mutagen.mp4 import MP4

logger = logging.getLogger(__name__)


def plot_bpm_analysis(
    file_path: Path,
    y: np.ndarray,
    sample_rate: Union[int, float],
    beats: np.ndarray,
    bpm: float,
    onset_env: Optional[np.ndarray],
    config: 'BPMAnalysisConfig',
    use_hpss: bool,
    use_onset_strength: bool,
    duration: float,
    xlim: Optional[tuple[float, float]] = None,
) -> None:
    """
    Plot BPM analysis results with waveform, onset strength, and detected beats.

    Parameters
    ----------
    file_path : Path
        Path to the audio file.
    y : np.ndarray
        Audio time series.
    sample_rate : Union[int, float]
        Sample rate of the audio.
    beats : np.ndarray
        Array of beat frame indices.
    bpm : float
        Detected BPM value.
    onset_env : Optional[np.ndarray]
        Onset strength envelope (if computed).
    config : BPMAnalysisConfig
        Configuration used for analysis.
    use_hpss : bool
        Whether HPSS was used.
    use_onset_strength : bool
        Whether onset strength was computed.
    duration : float
        Duration of audio in seconds.
    xlim : Optional[tuple[float, float]], optional
        Time range (in seconds) to plot (default: None, shows full duration).
    """
    plt.figure(figsize=(10, 5))

    # Determine time segment to plot
    if xlim is not None:
        t_start, t_end = xlim
        # Clip to valid range
        t_start = max(0, t_start)
        t_end = min(duration, t_end)
    else:
        t_start = 0
        t_end = duration

    # Calculate sample indices for the segment
    start_sample = int(t_start * sample_rate)
    end_sample = int(t_end * sample_rate)

    # Slice waveform for the segment
    y_segment = y[start_sample:end_sample]
    times_waveform = np.linspace(t_start, t_end, num=len(y_segment))

    # Plot waveform segment
    plt.plot(times_waveform, y_segment, alpha=0.5, label='Waveform')

    # Plot onset strength if it was computed
    if use_onset_strength and onset_env is not None:
        # Calculate frame indices for the segment
        start_frame = librosa.time_to_frames(
            t_start, sr=sample_rate, hop_length=config.hop_length)
        end_frame = librosa.time_to_frames(
            t_end, sr=sample_rate, hop_length=config.hop_length)

        # Normalize onset envelope for plotting
        max_val = np.max(onset_env) if getattr(onset_env, "size", 0) > 0 else 0.0
        if max_val > 0:
            onset_env_normalized = onset_env / max_val
        else:
            onset_env_normalized = np.array([])

        # Slice onset envelope
        onset_env_segment = onset_env_normalized[start_frame:end_frame]
        times_onset = librosa.frames_to_time(
            np.arange(start_frame, end_frame),
            sr=sample_rate,
            hop_length=config.hop_length,
        )
        plt.plot(times_onset, onset_env_segment, label='Onset Strength')
        vlines_ymax = onset_env_segment.max() if len(onset_env_segment) > 0 else 1.0
    else:
        vlines_ymax = np.abs(y_segment).max() if len(y_segment) > 0 else 1.0

    # Filter beats that fall within the segment
    times_beats = librosa.frames_to_time(
        beats,
        sr=sample_rate,
        hop_length=config.hop_length,
    )
    beats_in_segment = times_beats[(times_beats >= t_start) & (times_beats <= t_end)]

    # Plot detected beats in segment
    if len(beats_in_segment) > 0:
        plt.vlines(
            beats_in_segment,
            -vlines_ymax,
            vlines_ymax,
            color='r',
            alpha=0.75,
            linestyle='--',
            label='Beats'
        )

    plt.xlabel('Time (s)')

    # Add preprocessing info to title
    preproc_info = []
    if use_hpss:
        preproc_info.append("HPSS")
    if use_onset_strength:
        preproc_info.append("Onset")
    preproc_str = f" [{', '.join(preproc_info)}]" if preproc_info else " [Direct]"

    segment_info = f" [{t_start:.1f}s-{t_end:.1f}s]" if xlim is not None else ""
    plt.title(f'BPM Analysis for {file_path.name}{preproc_str}{segment_info} - {bpm:.2f} BPM')
    plt.legend()
    plt.tight_layout()
    plt.show()


@dataclass
class BPMAnalysisConfig:
    """
    Configuration for BPM analysis.

    Attributes
    ----------
    sr : Optional[int]
        Sample rate for audio loading (default: None, uses original sample rate).
        Lower sample rate speeds up processing.
    hop_length : int
        Number of samples between successive frames (default: 512).
    tightness : int
        Higher values result in more stable tempo estimation (default: 400).
    start_bpm : float
        Initial BPM guess to help the algorithm converge (default: 120.0).
    n_fft : int
        FFT window size for onset strength calculation (default: 512).
    aggregate : Callable[..., float]
        Function to aggregate frequency bins for onset strength (default: np.mean).
    fmax : Optional[float]
        Maximum frequency to consider in onset strength calculation
        (default: 5000.0, None uses Nyquist).
    n_mels : int
        Number of Mel bands to generate (default: 32).
    
    Example
    -------
    >>> # Custom configuration for faster processing
    >>> config = BPMAnalysisConfig(sr=11025, use_hpss=False)
    >>> result = analyze_bpm("track.mp3", config=config)
    """
    sr: Optional[int] = None  # Use None to load at original sample rate
    hop_length: int = 512
    tightness: int = 400
    start_bpm: float = 120.0
    n_fft: int = 512
    aggregate: Callable[..., float] = np.mean
    fmax: Optional[float] = 5000.0
    n_mels: int = 32


def analyze_bpm(
    file_path: Union[str, Path],
    use_hpss: bool = True,
    use_onset_strength: bool = True,
    config: Optional[BPMAnalysisConfig] = None,
    plot: bool = False,
    xlim: Optional[tuple[float, float]] = None,
) -> Dict[str, Union[str, float, int, None]]:
    """
    Analyze BPM of an audio file using librosa.

    Uses librosa's tempo estimation with beat tracking for robust BPM detection.
    Works well for a wide range of tempos (60-200 BPM) and handles tempo drift.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file to analyze.
    use_hpss : bool
        If True, use harmonic-percussive source separation (default: True).
    use_onset_strength : bool
        If True, compute onset strength envelope before beat tracking (default: True).
    config : Optional[BPMAnalysisConfig], optional
        Configuration object for analysis parameters. If None, uses default configuration.
    plot : bool, optional
        If True, plot the beat events against the onset strength envelope (default: False).
    xlim : Optional[tuple[float, float]], optional
        Time range (in seconds) to plot, e.g., (10, 20) for 10-20 seconds
        (default: None, shows full duration).
    
    Returns
    -------
    Dict[str, Union[str, float, int, None]]
        Dictionary containing:
        - file_path: str - Path to the analyzed file
        - bpm: float - Detected BPM value
        - confidence: float - Confidence score (0-1) based on beat strength
        - duration: float - Duration of audio in seconds
        - samples: int - Number of audio samples analyzed

    Example
    -------
    >>> # Default configuration
    >>> result = analyze_bpm("track.mp3")
    >>> print(f"BPM: {result['bpm']:.2f}")
    >>> 
    >>> # Custom configuration for faster processing
    >>> config = BPMAnalysisConfig(sr=11025)
    >>> result = analyze_bpm("track.mp3", use_hpss=False, use_onset_strength=False, config=config)
    >>> 
    >>> # Plot specific time segment
    >>> result = analyze_bpm("track.mp3", plot=True, xlim=(30, 60))
    >>> 
    >>> # High accuracy configuration
    >>> config = BPMAnalysisConfig(sr=44100, tightness=500, n_fft=2048)
    >>> result = analyze_bpm("track.mp3", config=config)
    """
    # Use default config if not provided
    if config is None:
        config = BPMAnalysisConfig()
    file_path = Path(file_path)

    result = {
        'file_path': str(file_path),
        'duration': None,
        'samples': None,
        'bpm': None,
        'confidence': None,
    }

    onset_env = None
    try:
        # Load audio file
        y, sample_rate = librosa.load(str(file_path), sr=config.sr)
        result['duration'] = float(librosa.get_duration(y=y, sr=sample_rate))
        result['samples'] = len(y)

        # Optional: Separate into harmonic and percussive components
        if use_hpss:
            _, y_percussive = librosa.effects.hpss(y)
            y_for_analysis = y_percussive
        else:
            y_for_analysis = y

        # Optional: Compute onset envelope for better beat detection
        if use_onset_strength:
            onset_env = librosa.onset.onset_strength(
                y=y_for_analysis,
                sr=sample_rate,
                hop_length=config.hop_length,
                fmax=config.fmax,
                aggregate=config.aggregate,
                n_fft=config.n_fft,
                n_mels=config.n_mels,
            )

            # Detect tempo using dynamic programming beat tracker with onset envelope
            tempo, beats = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sample_rate,
                hop_length=config.hop_length,
                start_bpm=config.start_bpm,
                tightness=config.tightness,
            )
        else:
            # Direct beat tracking without onset envelope
            tempo, beats = librosa.beat.beat_track(
                y=y_for_analysis,
                sr=sample_rate,
                hop_length=config.hop_length,
                start_bpm=config.start_bpm,
                tightness=config.tightness,
            )

        result['bpm'] = float(tempo)

        # Calculate confidence based on beat strength variance
        # Lower variance = more consistent beats = higher confidence
        if len(beats) > 1:
            beat_frames = librosa.frames_to_samples(
                beats,
                hop_length=config.hop_length,
            )
            beat_strengths = y[beat_frames]

            if len(beat_strengths) > 0:
                strength_std = np.std(np.abs(beat_strengths))
                strength_mean = np.mean(np.abs(beat_strengths))

                # Normalize confidence to 0-1 range
                # Lower relative std = higher confidence
                if strength_mean > 0:
                    confidence = 1.0 - min(strength_std / strength_mean, 1.0)
                    result['confidence'] = float(confidence)
                else:
                    result['confidence'] = 0.5
            else:
                result['confidence'] = 0.5
        else:
            result['confidence'] = 0.3  # Low confidence if few beats detected

        logger.info(
            "BPM analysis complete for %s: %.2f BPM (confidence: %.2f)",
            file_path.name, result['bpm'], result['confidence']
        )

        if plot:
            plot_bpm_analysis(
                file_path=file_path,
                y=y,
                sample_rate=sample_rate,
                beats=beats,
                bpm=result['bpm'],
                onset_env=onset_env,
                config=config,
                use_hpss=use_hpss,
                use_onset_strength=use_onset_strength,
                duration=result['duration'],
                xlim=xlim,
            )

    except (FileNotFoundError, RuntimeError, ValueError, IOError) as e:
        logger.error("Error analyzing BPM for %s: %s", file_path, str(e))
        result['bpm'] = None
        result['confidence'] = 0.0

    return result


def write_bpm_tag(file_path: Union[str, Path], bpm: float) -> bool:
    """
    Write BPM value to audio file tags.

    Supports MP3 (ID3v2), FLAC, M4A/MP4, and OGG Vorbis formats.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file.
    bpm : float
        BPM value to write to the file.

    Returns
    -------
    bool
        True if successful, False otherwise.

    Example
    -------
    >>> success = write_bpm_tag("track.mp3", 128.5)
    """
    file_path = Path(file_path)

    try:
        audio = File(str(file_path))

        if audio is None:
            logger.error("Could not load file: %s", file_path)
            return False

        # Round BPM to integer for tag writing
        bpm_int = int(round(bpm))

        # Handle MP3 files (ID3v2 tags)
        if file_path.suffix.lower() == '.mp3':
            if audio.tags is None:
                audio.add_tags()
            audio.tags['TBPM'] = TBPM(encoding=3, text=str(bpm_int))

        # Handle FLAC files
        elif isinstance(audio, FLAC):
            audio['BPM'] = str(bpm_int)

        # Handle MP4/M4A files
        elif isinstance(audio, MP4):
            audio['tmpo'] = [bpm_int]

        # Handle OGG Vorbis files
        elif hasattr(audio, 'tags') and audio.tags is not None:
            audio['BPM'] = str(bpm_int)

        else:
            logger.warning("Unsupported audio format for %s", file_path)
            return False

        audio.save()
        logger.info("Successfully wrote BPM %d to %s", bpm_int, file_path.name)
        return True

    except (MutagenError, FileNotFoundError, OSError, ValueError, TypeError) as e:
        logger.error("Error writing BPM tag to %s: %s", file_path, str(e))
        return False


def analyze_and_tag_bpm(
    file_path: Union[str, Path],
    write_tag: bool = True,
) -> Dict[str, Union[str, float, int, None]]:
    """
    Analyze BPM of an audio file and optionally write it to the file's tags.

    This is the main entry point for BPM detection and tagging.

    Parameters
    ----------
    file_path : Union[str, Path]
        Path to the audio file to analyze.
    write_tag : bool, optional
        If True, write the detected BPM to the file's tags (default: True).

    Returns
    -------
    Dict[str, Union[str, float, int, None]]
        Dictionary containing:
        - file_path: str - Path to the analyzed file
        - bpm: float - Detected BPM value
        - confidence: float - Confidence score (0-1)
        - duration: float - Duration of audio in seconds
        - samples: int - Number of audio samples analyzed

    Example
    -------
    >>> from aft.bpm import analyze_and_tag_bpm
    >>> result = analyze_and_tag_bpm("track.mp3", write_tag=True)
    >>> print(f"Detected BPM: {result['bpm']:.2f} (confidence: {result['confidence']:.2%})")
    """

    result = analyze_bpm(file_path)

    if write_tag and result['bpm'] is not None:
        # Ensure the BPM value is a float before passing to write_bpm_tag
        bpm_val = result['bpm']
        try:
            bpm_float = float(bpm_val)
            success = write_bpm_tag(file_path, bpm_float)
            if not success:
                logger.warning("BPM detected but could not write tag for %s", file_path)
        except (TypeError, ValueError):
            logger.error("Invalid BPM value (%r) for %s; skipping tag write", bpm_val, file_path)

    return result


def batch_analyze_bpm(
    file_paths: list[Union[str, Path]],
    write_tags: bool = True
) -> list[Dict[str, Union[str, float, int, None]]]:
    """
    Analyze BPM for multiple audio files.

    Parameters
    ----------
    file_paths : list[Union[str, Path]]
        List of paths to audio files to analyze.
    write_tags : bool, optional
        If True, write detected BPM values to file tags (default: True).

    Returns
    -------
    list[Dict[str, Union[str, float, int, None]]]
        List of result dictionaries for each file.

    Example
    -------
    >>> files = ["track1.mp3", "track2.mp3", "track3.mp3"]
    >>> results = batch_analyze_bpm(files)
    >>> avg_bpm = sum(r['bpm'] for r in results if r['bpm']) / len(results)
    """
    results = []

    for file_path in file_paths:
        result = analyze_and_tag_bpm(file_path, write_tag=write_tags)
        results.append(result)

    return results
