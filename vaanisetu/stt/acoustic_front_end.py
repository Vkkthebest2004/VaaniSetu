"""
Acoustic Front-End Signal Conditioner for iTantra Neural Transceiver.

Prepares raw microphone audio for neural STT inference through:
1. DC Offset Removal (centering signal around zero).
2. High-Frequency Pre-Emphasis (boosting retroflex & dental consonant formants).
3. Spectral Noise Gating (attenuating low-energy background acoustic noise).
4. Dynamic Range AGC / Soft Tanh Limiting (equalizing speaker volume variance).
5. Syllable-Preserving VAD Padding (preventing clipping of initial plosives and trailing matras).
"""

import numpy as np
from typing import Tuple, List, Optional


class AcousticFrontEnd:
    """
    Zero-latency acoustic pre-processor that conditions noisy, low-amplitude,
    or distance-variable microphone signals before passing to the neural recognizer.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        pre_emphasis_alpha: float = 0.97,
        noise_gate_threshold: float = 0.0035,
        target_peak: float = 0.85,
    ):
        self.sample_rate = sample_rate
        self.alpha = pre_emphasis_alpha
        self.noise_gate_thresh = noise_gate_threshold
        self.target_peak = target_peak

    def remove_dc_offset(self, audio: np.ndarray) -> np.ndarray:
        """Subtract DC component to center waveform around 0.0."""
        if len(audio) == 0:
            return audio
        return audio - np.mean(audio)

    def apply_pre_emphasis(self, audio: np.ndarray) -> np.ndarray:
        """
        Pre-emphasis filter: y[n] = x[n] - alpha * x[n-1].
        Flattens glottal spectral tilt, boosting high frequencies (>1kHz)
        where critical Indic retroflex consonants (ट, ठ, ड, ढ) and fricatives reside.
        """
        if len(audio) <= 1:
            return audio
        return np.append(audio[0], audio[1:] - self.alpha * audio[:-1])

    def apply_spectral_noise_gate(
        self,
        audio: np.ndarray,
        frame_ms: int = 20,
        attenuation_factor: float = 0.2,
    ) -> np.ndarray:
        """
        Attenuates frames whose energy is below ambient noise threshold.
        Cleans background room rumble without distorting voice formants.
        """
        if len(audio) == 0:
            return audio

        frame_len = int(self.sample_rate * frame_ms / 1000)
        if frame_len <= 0 or len(audio) < frame_len:
            return audio

        output = audio.copy()
        num_frames = len(audio) // frame_len

        for i in range(num_frames):
            start = i * frame_len
            end = start + frame_len
            frame = output[start:end]
            rms = np.sqrt(np.mean(frame ** 2))
            if rms < self.noise_gate_thresh:
                output[start:end] = frame * attenuation_factor

        return output

    def apply_dynamic_range_agc(self, audio: np.ndarray) -> np.ndarray:
        """
        Soft Dynamic Range Compression (AGC) using hyperbolic tangent limiter.
        Normalizes quiet signals while preventing clipping on loud shouts.
        """
        if len(audio) == 0:
            return audio

        peak = float(np.max(np.abs(audio)))
        if peak < 1e-6:
            return audio

        # Soft-knee tanh curve normalized to smoothly cap at target_peak
        normalized = audio / peak
        compressed = (np.tanh(normalized * 1.5) / np.tanh(1.5)) * self.target_peak
        return compressed.astype(np.float32)

    def pad_vad_boundaries(
        self,
        audio: np.ndarray,
        pre_padding_ms: int = 120,
        hangover_ms: int = 220,
    ) -> np.ndarray:
        """
        Pads beginning and end of speech segments with gentle ramped silence
        so neural STT doesn't miss the initial plosive or trailing vowel matra.
        """
        pre_samples = int(self.sample_rate * pre_padding_ms / 1000)
        hangover_samples = int(self.sample_rate * hangover_ms / 1000)

        pre_pad = np.zeros(pre_samples, dtype=np.float32)
        post_pad = np.zeros(hangover_samples, dtype=np.float32)

        return np.concatenate([pre_pad, audio, post_pad]).astype(np.float32)

    def process(
        self,
        audio: np.ndarray,
        apply_padding: bool = False,
        for_whisper: bool = False,
    ) -> np.ndarray:
        """
        Runs the complete acoustic front-end conditioning pipeline.
        Returns clean, normalized, formant-enhanced float32 audio.

        Args:
            audio: 1D float32 audio samples.
            apply_padding: If True, adds pre/post boundary padding.
            for_whisper: If True, preserves natural speech spectral tilt by applying
                         DC offset removal and AGC limiting without high-frequency
                         pre-emphasis (which distorts Whisper's log-mel filterbank).
        """
        audio = np.asarray(audio, dtype=np.float32).flatten()
        if len(audio) == 0:
            return audio

        if for_whisper:
            # For Whisper: maintain natural speech spectral balance and baseline
            audio = self.apply_dynamic_range_agc(audio)
            if apply_padding:
                audio = self.pad_vad_boundaries(audio)
            return audio.astype(np.float32)

        # 1. DC offset removal
        audio = self.remove_dc_offset(audio)

        # Standard acoustic front-end for legacy / CTC models:
        # 2. Spectral noise gate
        audio = self.apply_spectral_noise_gate(audio)

        # 3. High-frequency pre-emphasis
        audio = self.apply_pre_emphasis(audio)

        # 4. Soft dynamic range compression & gain normalization
        audio = self.apply_dynamic_range_agc(audio)

        # 5. Boundary padding if requested
        if apply_padding:
            audio = self.pad_vad_boundaries(audio)

        return audio.astype(np.float32)


# Alias for TinyML acoustic conditioning specification
TinyMLAcousticFrontEnd = AcousticFrontEnd
