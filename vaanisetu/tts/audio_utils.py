"""
Audio utilities for TTS — WAV output and playback.
"""

import numpy as np
import soundfile as sf


def save_audio(
    audio: np.ndarray,
    output_path: str,
    sample_rate: int = 16000,
) -> None:
    """
    Save audio data to a WAV file.

    Args:
        audio: Float32 or int16 audio array
        output_path: Path to save the WAV file
        sample_rate: Sample rate in Hz
    """
    sf.write(output_path, audio, sample_rate)


def play_audio(
    audio: np.ndarray,
    sample_rate: int = 16000,
    blocking: bool = True,
) -> None:
    """
    Play audio data through the default speakers.

    Args:
        audio: Float32 audio array
        sample_rate: Sample rate in Hz
        blocking: If True, block until playback completes
    """
    import sounddevice as sd
    sd.play(audio, sample_rate)
    if blocking:
        sd.wait()


def play_file(audio_path: str) -> None:
    """Play a WAV file through the default speakers."""
    audio, sr = sf.read(audio_path, dtype="float32")
    play_audio(audio, sr)


def normalize_audio(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """
    Normalize audio to a target peak level in dB.

    Args:
        audio: Float32 audio array
        target_db: Target peak level in dB (default: -3.0 dB)

    Returns:
        Normalized audio array
    """
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio

    target_peak = 10 ** (target_db / 20)
    return (audio * target_peak / peak).astype(np.float32)
