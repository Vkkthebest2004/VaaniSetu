"""
VaaniSetu STT — Speech-to-Text Module

Fully offline speech recognition supporting all 10 Indian languages
and English using sherpa-onnx with quantized Whisper and Zipformer models.

Usage:
    from vaanisetu.stt import MultilingualSTTEngine, SherpaSTTEngine

    # Multilingual STT (Hindi, Bengali, Tamil, Telugu, etc.)
    engine = MultilingualSTTEngine()
    text = engine.transcribe("recording.wav", language="hi")
    print(text)

    # Lightweight English Zipformer
    en_engine = SherpaSTTEngine()
    en_text = en_engine.transcribe("english.wav")
"""

from .engine import SherpaSTTEngine
from .multilingual_whisper import MultilingualSTTEngine
from .indic_normalizer import IndicScriptNormalizer
from .config import STTConfig, default_stt_config

__all__ = [
    "MultilingualSTTEngine",
    "SherpaSTTEngine",
    "IndicScriptNormalizer",
    "STTConfig",
    "default_stt_config",
]
