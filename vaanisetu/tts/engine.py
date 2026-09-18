"""
TTS Engine — Core speech synthesis using sherpa-onnx.

Uses Piper VITS models via sherpa-onnx for lightweight,
fully offline text-to-speech synthesis.
"""

import time
import numpy as np
import sherpa_onnx
from typing import Optional
from pathlib import Path

from .config import TTSConfig, default_tts_config
from .audio_utils import save_audio, play_audio, normalize_audio


class SherpaTTSEngine:
    """
    Offline Text-to-Speech engine powered by sherpa-onnx.

    Uses a Piper VITS model (ONNX) for lightweight, fully offline
    speech synthesis that runs on the lowest-end devices.

    Usage:
        engine = SherpaTTSEngine()
        engine.synthesize("Hello, welcome to VaaniSetu", output_path="output.wav")
        engine.speak("This is a test")
    """

    def __init__(self, config: Optional[TTSConfig] = None, model_dir: Optional[str] = None):
        """
        Initialize the TTS engine.

        Args:
            config: Full TTSConfig object. If None, uses default config.
            model_dir: Shortcut to set model directory (overrides config.model_dir)
        """
        if config is None:
            config = default_tts_config()
        if model_dir is not None:
            config = TTSConfig(model_dir=model_dir)

        config.validate()
        self._config = config

        # Build sherpa-onnx TTS configuration
        tts_config = sherpa_onnx.OfflineTtsConfig()

        # Set VITS model paths
        tts_config.model.vits.model = config.model
        tts_config.model.vits.tokens = config.tokens
        tts_config.model.vits.length_scale = config.length_scale

        # Set espeak-ng data dir if available
        if config.data_dir:
            tts_config.model.vits.data_dir = config.data_dir

        # Performance settings
        tts_config.model.num_threads = config.num_threads
        tts_config.max_num_sentences = config.max_sentences

        # Create the TTS engine
        self._tts = sherpa_onnx.OfflineTts(tts_config)

        # Read the actual sample rate from the model
        self._sample_rate = self._tts.sample_rate
        config.sample_rate = self._sample_rate

        print(f"✅ TTS Engine loaded: {config.model_dir}")
        print(f"   Model: {Path(config.model).name}")
        print(f"   Sample rate: {self._sample_rate} Hz, Threads: {config.num_threads}")

    @property
    def sample_rate(self) -> int:
        """Output audio sample rate."""
        return self._sample_rate

    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        speed: Optional[float] = None,
        speaker_id: Optional[int] = None,
    ) -> np.ndarray:
        """
        Synthesize speech from text.

        Args:
            text: Text to convert to speech
            output_path: If provided, save the audio to this WAV file
            speed: Speaking speed (1.0 = normal, > 1.0 = faster, < 1.0 = slower)
            speaker_id: Speaker ID for multi-speaker models

        Returns:
            Audio data as float32 numpy array
        """
        if not text or not text.strip():
            return np.array([], dtype=np.float32)

        sid = speaker_id if speaker_id is not None else self._config.speaker_id
        spd = speed if speed is not None else self._config.speed

        start_time = time.perf_counter()

        # Generate audio using sherpa-onnx
        audio_obj = self._tts.generate(text, sid=sid, speed=spd)

        # Convert to numpy array
        audio = np.array(audio_obj.samples, dtype=np.float32)

        elapsed = time.perf_counter() - start_time
        duration = len(audio) / self._sample_rate

        print(f"🔊 Synthesized {duration:.1f}s audio in {elapsed:.2f}s "
              f"(RTF={elapsed/duration:.2f})" if duration > 0 else "")

        # Normalize audio to avoid clipping
        audio = normalize_audio(audio)

        # Save to file if requested
        if output_path:
            save_audio(audio, output_path, self._sample_rate)
            print(f"   Saved to: {output_path}")

        return audio

    def speak(
        self,
        text: str,
        speed: Optional[float] = None,
        speaker_id: Optional[int] = None,
        blocking: bool = True,
    ) -> None:
        """
        Synthesize and immediately play speech.

        Args:
            text: Text to speak
            speed: Speaking speed
            speaker_id: Speaker ID
            blocking: If True, block until playback finishes
        """
        audio = self.synthesize(text, speed=speed, speaker_id=speaker_id)

        if len(audio) > 0:
            play_audio(audio, self._sample_rate, blocking=blocking)

    def synthesize_to_file(
        self,
        text: str,
        output_path: str,
        speed: Optional[float] = None,
    ) -> float:
        """
        Convenience method: synthesize text and save directly to a file.

        Args:
            text: Text to convert
            output_path: Path to save the WAV file
            speed: Speaking speed

        Returns:
            Duration of the generated audio in seconds
        """
        audio = self.synthesize(text, output_path=output_path, speed=speed)
        return len(audio) / self._sample_rate if len(audio) > 0 else 0.0
