"""
STT Engine — Core speech recognition using sherpa-onnx.

Provides both offline (file-based) and streaming (real-time mic) transcription
using the Zipformer transducer model.
"""

import time
import numpy as np
import sherpa_onnx
from typing import Optional, Generator

from .config import STTConfig, default_stt_config
from .audio_utils import load_audio
from .vad import VoiceActivityDetector
from .acoustic_front_end import AcousticFrontEnd
from .tactical_rescorer import TacticalRescorer


class SherpaSTTEngine:
    """
    Offline Speech-to-Text engine powered by sherpa-onnx.

    Uses a Zipformer transducer model (int8 quantized) for
    lightweight, fully offline speech recognition.

    Usage:
        engine = SherpaSTTEngine()
        text = engine.transcribe("recording.wav")
        print(text)
    """

    def __init__(self, config: Optional[STTConfig] = None, model_dir: Optional[str] = None):
        """
        Initialize the STT engine.

        Args:
            config: Full STTConfig object. If None, uses default config.
            model_dir: Shortcut to set model directory (overrides config.model_dir)
        """
        if config is None:
            config = default_stt_config()
        if model_dir is not None:
            config = STTConfig(model_dir=model_dir)

        config.validate()
        self._config = config

        # Create the recognizer using the factory method (sherpa-onnx >= 1.10)
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=config.encoder,
            decoder=config.decoder,
            joiner=config.joiner,
            tokens=config.tokens,
            num_threads=config.num_threads,
            decoding_method=config.decoding_method,
            max_active_paths=config.max_active_paths,
        )

        # Lazy-init VAD (only if needed)
        self._vad: Optional[VoiceActivityDetector] = None

        # Acoustic front-end & tactical domain rescorer
        self._front_end = AcousticFrontEnd(sample_rate=config.sample_rate)
        self._rescorer = TacticalRescorer()

        print(f"✅ STT Engine loaded: {config.model_dir}")
        print(f"   Encoder: {config.encoder.split('/')[-1]}")
        print(f"   Threads: {config.num_threads}, Method: {config.decoding_method}")

    def _get_vad(self) -> VoiceActivityDetector:
        """Get or create VAD instance (lazy initialization)."""
        if self._vad is None:
            self._vad = VoiceActivityDetector(self._config)
        return self._vad

    def transcribe(
        self,
        audio_path: str,
        use_vad: Optional[bool] = None,
    ) -> str:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file (WAV, FLAC, OGG, etc.)
            use_vad: Whether to use VAD to segment audio first.
                     Defaults to config.vad_enabled.

        Returns:
            Transcribed text string
        """
        use_vad = use_vad if use_vad is not None else self._config.vad_enabled

        # Load and preprocess audio
        audio, sr = load_audio(audio_path, target_sr=self._config.sample_rate)
        audio = self._front_end.process(audio)

        start_time = time.perf_counter()

        if use_vad:
            text = self._transcribe_with_vad(audio)
        else:
            text = self._transcribe_audio(audio)

        text = self._rescorer.rescore(text)

        elapsed = time.perf_counter() - start_time
        audio_duration = len(audio) / self._config.sample_rate
        rtf = elapsed / audio_duration if audio_duration > 0 else 0

        print(f"📝 Transcription ({audio_duration:.1f}s audio in {elapsed:.2f}s, RTF={rtf:.2f})")

        return text

    def transcribe_array(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        use_vad: Optional[bool] = None,
    ) -> str:
        """
        Transcribe a numpy audio array to text.

        Args:
            audio: Float32 audio data
            sample_rate: Sample rate of the audio
            use_vad: Whether to use VAD

        Returns:
            Transcribed text string
        """
        use_vad = use_vad if use_vad is not None else self._config.vad_enabled

        # Ensure 1D float32 array
        audio = np.asarray(audio, dtype=np.float32).flatten()
        if len(audio) == 0:
            return ""

        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio ** 2)))

        # Silence Gate & Minimum Duration Check:
        # Zipformer requires at least 0.15s of audio to pass through Conv downsampling layers
        if len(audio) < int(self._config.sample_rate * 0.15) or (peak < 0.003 and rms < 0.0005):
            return ""

        # Resample if needed
        if sample_rate != self._config.sample_rate:
            from .audio_utils import _resample
            audio = _resample(audio, sample_rate, self._config.sample_rate)

        # Apply TinyML Acoustic Front-End conditioning (DC removal, noise gate, pre-emphasis, AGC)
        audio = self._front_end.process(audio)

        if use_vad:
            raw_text = self._transcribe_with_vad(audio)
        else:
            raw_text = self._transcribe_audio(audio)

        # Apply tactical domain rescoring & ITN
        return self._rescorer.rescore(raw_text)

    def _transcribe_audio(self, audio: np.ndarray) -> str:
        """Transcribe raw audio data without VAD."""
        min_samples = int(self._config.sample_rate * 0.3)
        if len(audio) < min_samples:
            padded = np.zeros(min_samples, dtype=np.float32)
            padded[:len(audio)] = audio
            audio = padded

        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._config.sample_rate, audio)
        self._recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def _transcribe_with_vad(self, audio: np.ndarray) -> str:
        """Transcribe audio using VAD with graceful fallback."""
        try:
            vad = self._get_vad()
            segments = vad.detect_speech_segments(audio)

            if segments:
                texts = []
                for start_t, end_t, segment_audio in segments:
                    text = self._transcribe_audio(segment_audio)
                    if text:
                        texts.append(text)
                if texts:
                    return " ".join(texts)
        except Exception as e:
            print(f"VAD error, falling back to direct recognition: {e}")

        # Fallback to direct transcription if VAD detected no segments
        return self._transcribe_audio(audio)

    def stream_from_mic(
        self,
        chunk_duration_ms: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Stream transcription from the microphone in real-time.

        Yields partial transcription results as the user speaks.
        Press Ctrl+C to stop.

        Args:
            chunk_duration_ms: Audio chunk size in milliseconds

        Yields:
            Partial transcription text
        """
        import sounddevice as sd

        chunk_ms = chunk_duration_ms or self._config.chunk_duration_ms
        chunk_samples = int(self._config.sample_rate * chunk_ms / 1000)

        print("🎤 Listening... (press Ctrl+C to stop)")

        # Use an online (streaming) recognizer for real-time
        # For now, we accumulate audio and do periodic offline recognition
        buffer = []
        silence_count = 0
        max_silence_chunks = int(1500 / chunk_ms)  # 1.5s of silence triggers recognition

        try:
            with sd.InputStream(
                samplerate=self._config.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_samples,
            ) as stream:
                while True:
                    chunk, _ = stream.read(chunk_samples)
                    chunk = chunk.flatten()

                    # Simple energy-based voice detection
                    energy = np.sqrt(np.mean(chunk ** 2))

                    if energy > 0.01:  # Speech detected
                        buffer.append(chunk)
                        silence_count = 0
                    else:
                        silence_count += 1

                        if buffer and silence_count >= max_silence_chunks:
                            # Silence after speech — transcribe the buffer
                            audio = np.concatenate(buffer)
                            text = self._transcribe_audio(audio)
                            buffer = []
                            silence_count = 0

                            if text:
                                yield text

        except KeyboardInterrupt:
            # Process any remaining audio in the buffer
            if buffer:
                audio = np.concatenate(buffer)
                text = self._transcribe_audio(audio)
                if text:
                    yield text
            print("\n🛑 Stopped listening.")
