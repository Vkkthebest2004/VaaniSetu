"""
iTantra Voice Activity Detection (iVAD) State Machine
Conforms to Section 18 of iTantra Technical Specification:
State Machine:
IDLE -> (speech detected) -> SPEAKING -> (silence threshold) -> POSSIBLE_END -> (confirmed silence) -> END_OF_UTTERANCE
Operates locally, continuously, with minimal CPU utilization.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
import numpy as np
import sherpa_onnx
from pathlib import Path


class VADState(Enum):
    IDLE = "IDLE"
    SPEAKING = "SPEAKING"
    POSSIBLE_END = "POSSIBLE_END"
    END_OF_UTTERANCE = "END_OF_UTTERANCE"


class iVADStateMachine:
    """
    Robust 4-state Voice Activity Detection engine.
    Wraps Silero VAD / Sherpa VAD with state transitions, hangover counters,
    and speech segment boundaries.
    """

    def __init__(
        self,
        vad_model_path: Optional[str] = None,
        sample_rate: int = 16000,
        threshold: float = 0.45,
        min_speech_duration_ms: float = 120.0,
        min_silence_duration_ms: float = 300.0,
        window_size_samples: int = 512
    ):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.window_size_samples = window_size_samples
        self.min_speech_samples = int(sample_rate * (min_speech_duration_ms / 1000.0))
        self.min_silence_samples = int(sample_rate * (min_silence_duration_ms / 1000.0))

        # Default model location
        if vad_model_path is None:
            vad_model_path = "models/vad/silero_vad.onnx"

        self.model_path = Path(vad_model_path)
        self._init_sherpa_vad()

        self.state = VADState.IDLE
        self.speech_frames_count = 0
        self.silence_frames_count = 0
        self.current_utterance_audio: List[np.ndarray] = []

    def _init_sherpa_vad(self):
        """Initialize the ONNX Silero VAD from Sherpa-ONNX."""
        if self.model_path.exists():
            vad_config = sherpa_onnx.VadModelConfig()
            vad_config.silero_vad.model = str(self.model_path)
            vad_config.silero_vad.threshold = self.threshold
            vad_config.silero_vad.min_silence_duration = 0.30
            vad_config.silero_vad.min_speech_duration = 0.12
            vad_config.silero_vad.window_size = self.window_size_samples
            vad_config.sample_rate = self.sample_rate

            self.vad = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=30)
            self._using_sherpa = True
        else:
            # Fallback to energy-based VAD if model file is not found
            self.vad = None
            self._using_sherpa = False

    def reset(self):
        """Reset state machine to IDLE."""
        if self._using_sherpa and self.vad:
            self.vad.clear()
        self.state = VADState.IDLE
        self.speech_frames_count = 0
        self.silence_frames_count = 0
        self.current_utterance_audio.clear()

    def process_chunk(self, chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process a chunk of 16kHz mono audio (typically 512 samples / 32ms).

        Returns:
            {
                "state": VADState,
                "is_speech": bool,
                "utterance_completed": bool,
                "utterance_audio": Optional[np.ndarray]
            }
        """
        # Ensure float32 1D
        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)
        if chunk.ndim > 1:
            chunk = np.mean(chunk, axis=1)

        is_speech = False

        if self._using_sherpa and self.vad:
            self.vad.accept_waveform(chunk)
            is_speech = self.vad.is_speech_detected()
        else:
            # Energy fallback
            rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
            is_speech = rms > 0.008

        utterance_completed = False
        completed_audio = None

        # State transitions
        if self.state == VADState.IDLE:
            if is_speech:
                self.speech_frames_count += len(chunk)
                self.current_utterance_audio.append(chunk)
                if self.speech_frames_count >= self.min_speech_samples:
                    self.state = VADState.SPEAKING
            else:
                self.speech_frames_count = 0
                self.current_utterance_audio.clear()

        elif self.state == VADState.SPEAKING:
            self.current_utterance_audio.append(chunk)
            if not is_speech:
                self.silence_frames_count = len(chunk)
                self.state = VADState.POSSIBLE_END
            else:
                self.silence_frames_count = 0

        elif self.state == VADState.POSSIBLE_END:
            self.current_utterance_audio.append(chunk)
            if not is_speech:
                self.silence_frames_count += len(chunk)
                if self.silence_frames_count >= self.min_silence_samples:
                    self.state = VADState.END_OF_UTTERANCE
                    utterance_completed = True
                    if self.current_utterance_audio:
                        completed_audio = np.concatenate(self.current_utterance_audio)
                    # Automatically transition back to IDLE
                    self.reset()
            else:
                # Speech resumed! Return to SPEAKING
                self.silence_frames_count = 0
                self.state = VADState.SPEAKING

        return {
            "state": self.state,
            "is_speech": is_speech,
            "utterance_completed": utterance_completed,
            "utterance_audio": completed_audio
        }
