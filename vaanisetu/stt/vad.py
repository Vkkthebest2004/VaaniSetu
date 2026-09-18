"""
Voice Activity Detection (VAD) — detects speech segments in audio.

Uses sherpa-onnx's built-in Silero VAD model for lightweight,
on-device voice activity detection.
"""

import numpy as np
import sherpa_onnx
from typing import Optional

from .config import STTConfig


class VoiceActivityDetector:
    """
    Lightweight VAD using Silero VAD via sherpa-onnx.

    Detects speech vs silence boundaries in audio streams,
    enabling efficient STT by only processing speech segments.
    """

    def __init__(self, config: Optional[STTConfig] = None):
        if config is None:
            from .config import default_stt_config
            config = default_stt_config()

        self._config = config
        self._sample_rate = config.sample_rate

        # Build VAD config using Silero VAD model
        vad_config = sherpa_onnx.VadModelConfig()
        if not config.vad_model:
            raise FileNotFoundError(
                "Silero VAD model path not configured. "
                "Download it to models/vad/silero_vad.onnx or specify in config."
            )
        vad_config.silero_vad.model = config.vad_model
        vad_config.silero_vad.threshold = config.vad_threshold
        vad_config.silero_vad.min_silence_duration = config.vad_min_silence_ms / 1000.0
        vad_config.silero_vad.min_speech_duration = config.vad_min_speech_ms / 1000.0
        vad_config.sample_rate = config.sample_rate

        self._vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=60)

    def detect_speech_segments(
        self,
        audio: np.ndarray,
    ) -> list[tuple[float, float, np.ndarray]]:
        """
        Detect speech segments in audio data.

        Args:
            audio: Float32 audio array at the configured sample rate

        Returns:
            List of (start_time, end_time, audio_segment) tuples
        """
        # Reset the VAD state for a new audio input
        self._vad.reset()

        # Feed audio in chunks (Silero VAD expects 512-sample windows for 16kHz)
        window_size = 512
        segments = []

        for i in range(0, len(audio), window_size):
            chunk = audio[i : i + window_size]
            if len(chunk) < window_size:
                # Pad the last chunk with zeros
                chunk = np.pad(chunk, (0, window_size - len(chunk)))
            self._vad.accept_waveform(chunk)

        # Flush remaining audio
        self._vad.flush()

        # Extract detected speech segments
        while not self._vad.empty():
            segment = self._vad.front
            start_sample = segment.start
            samples = np.array(segment.samples, dtype=np.float32)
            start_time = start_sample / self._sample_rate
            end_time = start_time + len(samples) / self._sample_rate
            segments.append((start_time, end_time, samples))
            self._vad.pop()

        return segments

    def has_speech(self, audio: np.ndarray) -> bool:
        """Quick check: does the audio contain any speech at all?"""
        segments = self.detect_speech_segments(audio)
        return len(segments) > 0
