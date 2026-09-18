"""
Unit tests for VaaniSetu TTS Engine
"""

import os
import pytest
import numpy as np
from vaanisetu.tts import SherpaTTSEngine, TTSConfig


@pytest.fixture(scope="module")
def tts_engine():
    config = TTSConfig(
        model_dir="models/tts/vits-piper-en_US-lessac-low",
    )
    return SherpaTTSEngine(config=config)


def test_tts_initialization(tts_engine):
    assert tts_engine is not None
    assert tts_engine._tts is not None
    assert tts_engine.sample_rate == 16000


def test_tts_synthesis(tts_engine):
    text = "Hello world from VaaniSetu"
    audio = tts_engine.synthesize(text)

    assert isinstance(audio, np.ndarray)
    assert len(audio) > 0
    # Minimum duration should be at least 0.5s (8000 samples at 16kHz)
    assert len(audio) > 8000


def test_tts_synthesize_to_file(tts_engine, tmp_path):
    output_path = tmp_path / "test_tts.wav"
    duration = tts_engine.synthesize_to_file("Testing audio save", str(output_path))

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    assert duration > 0.0
