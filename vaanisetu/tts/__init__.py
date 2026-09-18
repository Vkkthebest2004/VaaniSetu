"""
VaaniSetu TTS — Text-to-Speech Module

Fully offline speech synthesis using sherpa-onnx with
Piper VITS models supporting 10 Indian languages and English.

Usage:
    from vaanisetu.tts import IndicTTSEngine, SherpaTTSEngine

    tts = IndicTTSEngine()
    audio, duration = tts.synthesize("नमस्ते, स्थिति सामान्य है", language="hi")
"""

from .engine import SherpaTTSEngine
from .indic_tts import IndicTTSEngine
from .config import TTSConfig, default_tts_config

__all__ = [
    "IndicTTSEngine",
    "SherpaTTSEngine",
    "TTSConfig",
    "default_tts_config",
]
