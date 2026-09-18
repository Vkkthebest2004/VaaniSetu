"""
Audio utilities for STT — loading, resampling, and microphone capture.

Uses soundfile (C-backed, fastest) for file I/O and sounddevice for mic capture.
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional


def load_audio(
    audio_path: str,
    target_sr: int = 16000,
    mono: bool = True,
) -> tuple[np.ndarray, int]:
    """
    Load an audio file and resample to the target sample rate.

    Args:
        audio_path: Path to the audio file (WAV, FLAC, OGG, etc.)
        target_sr: Target sample rate in Hz (default: 16000 for STT models)
        mono: If True, convert to mono by averaging channels

    Returns:
        Tuple of (audio_data as float32 numpy array, sample_rate)
    """
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Read audio using soundfile (fast C backend via libsndfile)
    audio_data, file_sr = sf.read(audio_path, dtype="float32")

    # Convert to mono if needed
    if mono and audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    # Resample if sample rate doesn't match target
    if file_sr != target_sr:
        audio_data = _resample(audio_data, file_sr, target_sr)

    return audio_data, target_sr


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    Simple linear interpolation resampling.

    This avoids heavy dependencies like librosa/scipy for resampling,
    keeping the module lightweight for on-device deployment.
    For production, consider soxr if available.
    """
    if orig_sr == target_sr:
        return audio

    # Try to use soxr (high quality, already installed with librosa)
    try:
        import soxr
        return soxr.resample(audio, orig_sr, target_sr).astype(np.float32)
    except ImportError:
        pass

    # Fallback: linear interpolation (acceptable for speech)
    duration = len(audio) / orig_sr
    target_length = int(duration * target_sr)
    indices = np.linspace(0, len(audio) - 1, target_length)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def record_from_mic(
    duration_seconds: float,
    sample_rate: int = 16000,
    channels: int = 1,
) -> np.ndarray:
    """
    Record audio from the default microphone.

    Args:
        duration_seconds: Duration to record in seconds
        sample_rate: Recording sample rate
        channels: Number of audio channels (1 = mono)

    Returns:
        Audio data as float32 numpy array
    """
    import sounddevice as sd

    print(f"🎤 Recording for {duration_seconds:.1f}s...")
    audio = sd.rec(
        int(duration_seconds * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        dtype="float32",
    )
    sd.wait()  # Block until recording is complete
    print("✅ Recording complete.")

    # Flatten to 1D if mono
    if channels == 1:
        audio = audio.flatten()

    return audio


def audio_to_int16(audio: np.ndarray) -> np.ndarray:
    """Convert float32 audio [-1.0, 1.0] to int16 [-32768, 32767]."""
    return (audio * 32767).astype(np.int16)


def save_audio(
    audio: np.ndarray,
    output_path: str,
    sample_rate: int = 16000,
) -> None:
    """Save audio data to a WAV file."""
    sf.write(output_path, audio, sample_rate)
