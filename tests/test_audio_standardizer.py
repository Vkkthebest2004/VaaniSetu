"""
Tests for iTantra Audio Standardization and Telephone Pipeline.
"""

import numpy as np
import pytest
from audio.preprocessing.standardizer import AudioStandardizer
from audio.preprocessing.telephone import TelephoneSimulator


def test_standardizer_converts_stereo_to_mono():
    standardizer = AudioStandardizer()
    stereo_audio = np.random.normal(0, 0.2, (16000, 2)).astype(np.float32)
    processed, diag = standardizer.process_array(stereo_audio, sample_rate=16000)

    assert processed.ndim == 1
    assert len(processed) == 16000
    assert diag["original_channels"] == 2
    assert abs(np.mean(processed)) < 1e-4  # DC offset removed


def test_standardizer_detects_clipping_and_silence():
    standardizer = AudioStandardizer()

    # Clipped audio with alternating peaks
    clipped_audio = np.array([1.0, -1.0] * 500, dtype=np.float32)
    _, diag_clipped = standardizer.process_array(clipped_audio, sample_rate=16000, normalize_peak=False)
    assert diag_clipped["is_clipped"] is True

    # Silent audio
    silent_audio = np.zeros(1000, dtype=np.float32)
    _, diag_silent = standardizer.process_array(silent_audio, sample_rate=16000)
    assert diag_silent["is_silent"] is True


def test_telephone_simulator_applies_codec_and_bandpass():
    sim = TelephoneSimulator(sample_rate=16000)
    clean_audio = np.sin(2 * np.pi * 1000 * np.linspace(0, 0.5, 8000)).astype(np.float32)

    telephone_audio = sim.transform(clean_audio, snr_db=25.0, add_codec=True)

    assert telephone_audio.ndim == 1
    assert len(telephone_audio) == len(clean_audio)
    assert np.max(np.abs(telephone_audio)) <= 0.95
    # Verification that codec altered sample values
    assert not np.allclose(clean_audio, telephone_audio)
