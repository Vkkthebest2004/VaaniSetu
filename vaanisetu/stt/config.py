"""
STT Configuration — Model paths, sample rate, and inference settings.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# Project root is 3 levels up from this file (vaanisetu/stt/config.py → VaaniSetu/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class STTConfig:
    """Configuration for the Speech-to-Text engine."""

    # --- Model paths ---
    model_dir: str = ""

    # Transducer model files (set automatically from model_dir)
    encoder: str = ""
    decoder: str = ""
    joiner: str = ""
    tokens: str = ""

    # --- Audio settings ---
    sample_rate: int = 16000
    channels: int = 1

    # --- Inference settings ---
    num_threads: int = 2           # Keep low for low-end devices
    decoding_method: str = "greedy_search"  # "greedy_search" or "modified_beam_search"
    max_active_paths: int = 4      # Only used for modified_beam_search

    # --- VAD settings ---
    vad_enabled: bool = True
    vad_model: str = ""            # Path to silero_vad.onnx
    vad_threshold: float = 0.5     # Silero VAD speech probability threshold
    vad_min_silence_ms: int = 500  # Minimum silence duration to split segments
    vad_min_speech_ms: int = 250   # Minimum speech duration to keep

    # --- Streaming settings ---
    chunk_duration_ms: int = 100   # Audio chunk size for streaming (milliseconds)

    def __post_init__(self):
        """Auto-resolve model file paths from model_dir."""
        if self.model_dir:
            model_path = Path(self.model_dir)
            if not model_path.is_absolute():
                model_path = _PROJECT_ROOT / model_path

            self.model_dir = str(model_path)

            # Auto-detect encoder (prefer int8 quantized)
            if not self.encoder:
                for name in ["encoder-epoch-99-avg-1.int8.onnx", "encoder.int8.onnx", "encoder.onnx"]:
                    candidate = model_path / name
                    if candidate.exists():
                        self.encoder = str(candidate)
                        break

            # Auto-detect decoder
            if not self.decoder:
                for name in ["decoder-epoch-99-avg-1.onnx", "decoder.onnx"]:
                    candidate = model_path / name
                    if candidate.exists():
                        self.decoder = str(candidate)
                        break

            # Auto-detect joiner
            if not self.joiner:
                for name in ["joiner-epoch-99-avg-1.int8.onnx", "joiner.int8.onnx", "joiner.onnx"]:
                    candidate = model_path / name
                    if candidate.exists():
                        self.joiner = str(candidate)
                        break

            # Auto-detect tokens
            if not self.tokens:
                candidate = model_path / "tokens.txt"
                if candidate.exists():
                    self.tokens = str(candidate)

        # Auto-detect VAD model
        if not self.vad_model:
            candidates = [
                _PROJECT_ROOT / "models" / "vad" / "silero_vad.onnx",
                Path("models/vad/silero_vad.onnx"),
            ]
            for c in candidates:
                if c.exists():
                    self.vad_model = str(c.resolve())
                    break

    def validate(self) -> None:
        """Raise an error if required model files are missing."""
        missing = []
        for attr in ["encoder", "decoder", "joiner", "tokens"]:
            path = getattr(self, attr)
            if not path:
                missing.append(attr)
            elif not os.path.isfile(path):
                missing.append(f"{attr} ({path})")

        if missing:
            raise FileNotFoundError(
                f"Missing STT model files: {', '.join(missing)}. "
                f"Run 'python scripts/download_models.py' to fetch them."
            )


def default_stt_config() -> STTConfig:
    """Return the default STT config pointing to the bundled Zipformer model."""
    return STTConfig(
        model_dir="models/stt/sherpa-onnx-zipformer-small-en-2023-06-26",
    )
