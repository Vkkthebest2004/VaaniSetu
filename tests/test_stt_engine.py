"""
Unit tests for VaaniSetu STT Engine
"""

from pathlib import Path
import pytest
from vaanisetu.stt import SherpaSTTEngine, STTConfig


@pytest.fixture(scope="module")
def stt_engine():
    config = STTConfig(
        model_dir="models/stt/sherpa-onnx-zipformer-small-en-2023-06-26",
    )
    return SherpaSTTEngine(config=config)


def test_stt_initialization(stt_engine):
    assert stt_engine is not None
    assert stt_engine._recognizer is not None


def test_stt_transcription_sample_0(stt_engine):
    test_wav = Path("models/stt/sherpa-onnx-zipformer-small-en-2023-06-26/test_wavs/0.wav")
    assert test_wav.exists()

    text = stt_engine.transcribe(str(test_wav), use_vad=False)
    assert len(text) > 0
    assert "YELLOW LAMPS" in text


def test_stt_transcription_with_vad(stt_engine):
    test_wav = Path("models/stt/sherpa-onnx-zipformer-small-en-2023-06-26/test_wavs/8k.wav")
    assert test_wav.exists()

    text = stt_engine.transcribe(str(test_wav), use_vad=True)
    assert len(text) > 0
    assert "HESTER PRYNNE" in text
