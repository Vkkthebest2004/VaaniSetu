"""
TTS Configuration — Model paths and synthesis settings.
"""

import os
from dataclasses import dataclass
from pathlib import Path


# Project root is 3 levels up from this file (vaanisetu/tts/config.py → VaaniSetu/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class TTSConfig:
    """Configuration for the Text-to-Speech engine."""

    # --- Model paths ---
    model_dir: str = ""

    # VITS/Piper model files (auto-resolved from model_dir)
    model: str = ""           # .onnx model file
    tokens: str = ""          # tokens.txt
    data_dir: str = ""        # espeak-ng-data directory

    # --- Audio settings ---
    sample_rate: int = 16000  # Output sample rate (set by model, typically 16000 or 22050)

    # --- Synthesis settings ---
    num_threads: int = 2      # Keep low for low-end devices
    speed: float = 1.0        # Speaking rate (0.5 = half speed, 2.0 = double speed)
    speaker_id: int = 0       # Speaker ID for multi-speaker models (0 for single-speaker)
    length_scale: float = 1.0 # Duration scaling (lower = faster speech)

    # --- Output settings ---
    max_sentences: int = 2    # Maximum sentences to synthesize in one batch

    def __post_init__(self):
        """Auto-resolve model file paths from model_dir."""
        if self.model_dir:
            model_path = Path(self.model_dir)
            if not model_path.is_absolute():
                model_path = _PROJECT_ROOT / model_path

            self.model_dir = str(model_path)

            # Auto-detect the .onnx model file
            if not self.model:
                for f in sorted(model_path.glob("*.onnx")):
                    self.model = str(f)
                    break

            # Auto-detect tokens.txt
            if not self.tokens:
                candidate = model_path / "tokens.txt"
                if candidate.exists():
                    self.tokens = str(candidate)

            # Auto-detect espeak-ng-data directory
            if not self.data_dir:
                candidate = model_path / "espeak-ng-data"
                if candidate.is_dir():
                    self.data_dir = str(candidate)

    def validate(self) -> None:
        """Raise an error if required model files are missing."""
        missing = []
        if not self.model or not os.path.isfile(self.model):
            missing.append(f"model ({self.model or 'not set'})")
        if not self.tokens or not os.path.isfile(self.tokens):
            missing.append(f"tokens ({self.tokens or 'not set'})")
        # data_dir is optional (not all models need espeak-ng-data)

        if missing:
            raise FileNotFoundError(
                f"Missing TTS model files: {', '.join(missing)}. "
                f"Run 'python scripts/download_models.py' to fetch them."
            )


def default_tts_config() -> TTSConfig:
    """Return the default TTS config pointing to the bundled Piper model."""
    return TTSConfig(
        model_dir="models/tts/vits-piper-en_US-lessac-low",
    )
