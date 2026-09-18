"""
iTantra Audio Standardization Pipeline
Conforms to Section 13 of iTantra Technical Specification:
Standard: 16 kHz, Mono, 16-bit PCM WAV.
Pipeline: RAW AUDIO -> Decode -> Validate -> Resample 16kHz -> Mono -> Check clipping/silence -> Normalize -> Save.
Preserves raw files without destructive overwriting.
"""

import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np
import scipy.io.wavfile as wavfile
from scipy import signal


class AudioStandardizer:
    """
    Standardizes arbitrary audio into 16 kHz, Mono, 16-bit PCM WAV format.
    Validates audio health, detects digital clipping, and removes DC offsets.
    """

    TARGET_SAMPLE_RATE = 16000
    CLIPPING_THRESHOLD = 0.999
    SILENCE_RMS_THRESHOLD = 0.0005

    def __init__(self, target_sample_rate: int = 16000, target_peak: float = 0.90):
        self.target_sample_rate = target_sample_rate
        self.target_peak = target_peak

    def process_array(
        self,
        audio: np.ndarray,
        sample_rate: int,
        normalize_peak: bool = True
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Process an in-memory audio array to standard 16kHz mono float32 format.

        Returns:
            processed_audio: np.ndarray (float32, 16kHz mono, range [-1.0, 1.0])
            diagnostics: dict with audio quality diagnostics
        """
        diagnostics = {
            "original_sample_rate": sample_rate,
            "original_channels": 1 if audio.ndim == 1 else audio.shape[1],
            "is_clipped": False,
            "is_silent": False,
            "duration_sec": 0.0,
            "peak_before": 0.0,
            "peak_after": 0.0,
            "rms": 0.0,
        }

        # Convert to float32 in [-1.0, 1.0]
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0
        else:
            audio = audio.astype(np.float32)

        # Convert stereo/multi-channel to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Check clipping before DC offset removal or resampling
        peak_raw = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        diagnostics["peak_before"] = peak_raw
        if peak_raw >= self.CLIPPING_THRESHOLD:
            diagnostics["is_clipped"] = True

        # Remove DC offset
        audio = audio - np.mean(audio)

        # Resample to target sample rate if needed
        if sample_rate != self.target_sample_rate and len(audio) > 0:
            num_target_samples = int(round(len(audio) * float(self.target_sample_rate) / sample_rate))
            audio = signal.resample(audio, num_target_samples).astype(np.float32)

        # RMS & Silence detection
        rms = float(np.sqrt(np.mean(audio ** 2))) if len(audio) > 0 else 0.0
        diagnostics["rms"] = rms
        if rms < self.SILENCE_RMS_THRESHOLD:
            diagnostics["is_silent"] = True

        # Peak normalization if appropriate
        curr_peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        if normalize_peak and curr_peak > 1e-6:
            gain = self.target_peak / curr_peak
            audio = audio * gain

        diagnostics["peak_after"] = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        diagnostics["duration_sec"] = len(audio) / float(self.target_sample_rate)

        return audio, diagnostics

    def standardize_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        normalize_peak: bool = True
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Standardize an audio file and save as 16-bit PCM WAV.
        Does NOT overwrite input if output_path is different.
        """
        input_p = Path(input_path)
        if not input_p.exists():
            raise FileNotFoundError(f"Audio file not found: {input_path}")

        # Read input WAV
        sr, raw = wavfile.read(str(input_p))

        processed, diag = self.process_array(raw, sr, normalize_peak=normalize_peak)

        if output_path is None:
            # Default to appending _std.wav in same directory
            output_p = input_p.with_name(f"{input_p.stem}_std.wav")
        else:
            output_p = Path(output_path)
            output_p.parent.mkdir(parents=True, exist_ok=True)

        # Convert back to 16-bit PCM
        pcm16 = np.clip(processed * 32767.0, -32768.0, 32767.0).astype(np.int16)
        wavfile.write(str(output_p), self.target_sample_rate, pcm16)

        return str(output_p), diag
