"""
iTantra Telephone Audio Robustness Pipeline
Conforms to Section 14 of iTantra Technical Specification:
Pipeline:
Clean audio -> Bandpass filter (300 Hz - 3400 Hz) -> 8kHz Codec Simulation (G.711 mu-law / A-law)
-> Additive Noise -> Acoustic Reverberation -> Volume variation -> Telephone Test Sample.
"""

import numpy as np
from scipy import signal
from typing import Tuple, Optional


class TelephoneSimulator:
    """
    Simulates realistic telephone channel degradation, acoustic reflections,
    and G.711 companding codecs for training and evaluating robustness.
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

        # 300 Hz - 3400 Hz Butterworth Bandpass Filter (Telephone telephony standard)
        nyq = 0.5 * sample_rate
        low = 300.0 / nyq
        high = 3400.0 / nyq
        self.b_bandpass, self.a_bandpass = signal.butter(4, [low, high], btype='band')

    def apply_telephone_filter(self, audio: np.ndarray) -> np.ndarray:
        """Apply 300Hz - 3400Hz telephone bandpass filtering."""
        if len(audio) < 16:
            return audio
        return signal.lfilter(self.b_bandpass, self.a_bandpass, audio).astype(np.float32)

    def simulate_g711_mulaw(self, audio: np.ndarray, mu: float = 255.0) -> np.ndarray:
        """
        Simulate G.711 mu-law companding codec (8-bit logarithmic quantization).
        Sign(x) * ln(1 + mu*|x|) / ln(1 + mu), quantized to 8 bits, then expanded back.
        """
        audio = np.clip(audio, -1.0, 1.0)
        # Compression
        compressed = np.sign(audio) * np.log1p(mu * np.abs(audio)) / np.log1p(mu)
        # 8-bit Quantization (256 discrete levels)
        quantized = np.round(compressed * 127.0) / 127.0
        # Expansion
        expanded = np.sign(quantized) * ((1.0 + mu) ** np.abs(quantized) - 1.0) / mu
        return expanded.astype(np.float32)

    def add_line_noise(self, audio: np.ndarray, snr_db: float = 20.0) -> np.ndarray:
        """Add realistic Gaussian electrical line noise at specified SNR (dB)."""
        signal_power = np.mean(audio ** 2)
        if signal_power < 1e-9:
            return audio
        noise_power = signal_power / (10.0 ** (snr_db / 10.0))
        noise = np.random.normal(0.0, np.sqrt(noise_power), size=audio.shape).astype(np.float32)
        return (audio + noise).astype(np.float32)

    def add_reverberation(self, audio: np.ndarray, delay_ms: float = 35.0, decay: float = 0.3) -> np.ndarray:
        """Simulate single/multi-reflection room reverberation."""
        delay_samples = int(self.sample_rate * (delay_ms / 1000.0))
        if delay_samples <= 0 or delay_samples >= len(audio):
            return audio
        reverbed = np.copy(audio)
        reverbed[delay_samples:] += decay * audio[:-delay_samples]
        return reverbed.astype(np.float32)

    def apply_volume_variation(self, audio: np.ndarray, min_gain: float = 0.5, max_gain: float = 1.4) -> np.ndarray:
        """Simulate user speaking closer or farther from the telephone receiver."""
        gain = np.random.uniform(min_gain, max_gain)
        return (audio * gain).astype(np.float32)

    def transform(
        self,
        audio: np.ndarray,
        snr_db: float = 18.0,
        reverb_decay: float = 0.25,
        add_codec: bool = True
    ) -> np.ndarray:
        """
        Run the full telephone pipeline:
        Clean -> Bandpass -> G.711 mu-law -> Line noise -> Reverb -> Gain
        """
        # 1. Bandpass filter
        y = self.apply_telephone_filter(audio)

        # 2. G.711 Codec simulation
        if add_codec:
            y = self.simulate_g711_mulaw(y)

        # 3. Add electrical line noise
        y = self.add_line_noise(y, snr_db=snr_db)

        # 4. Add subtle acoustic reverberation
        y = self.add_reverberation(y, delay_ms=30.0, decay=reverb_decay)

        # 5. Peak limiter
        peak = np.max(np.abs(y)) if len(y) > 0 else 0.0
        if peak > 0.95:
            y = y / peak * 0.95

        return y.astype(np.float32)
