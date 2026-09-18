"""
Unit tests for AcousticFrontEnd signal conditioner.
"""

import numpy as np
import pytest
from vaanisetu.stt.acoustic_front_end import AcousticFrontEnd


def test_front_end_initialization():
    afe = AcousticFrontEnd(sample_rate=16000)
    assert afe.sample_rate == 16000
    assert afe.alpha == 0.97


def test_dc_offset_removal():
    afe = AcousticFrontEnd()
    audio = np.ones(1600, dtype=np.float32) * 0.5
    cleaned = afe.remove_dc_offset(audio)
    assert np.abs(np.mean(cleaned)) < 1e-6


def test_pre_emphasis_enhances_high_frequencies():
    afe = AcousticFrontEnd(pre_emphasis_alpha=0.97)
    # Step signal: high frequency change
    audio = np.array([0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float32)
    emphasized = afe.apply_pre_emphasis(audio)
    assert len(emphasized) == len(audio)
    assert emphasized[1] == 1.0 - 0.97 * 0.0


def test_noise_gate_attenuation():
    afe = AcousticFrontEnd(noise_gate_threshold=0.01)
    # Low amplitude noise below threshold
    noise = np.random.normal(0, 0.002, 1600).astype(np.float32)
    initial_peak = np.max(np.abs(noise))
    gated = afe.apply_spectral_noise_gate(noise, frame_ms=20, attenuation_factor=0.2)
    gated_peak = np.max(np.abs(gated))
    assert gated_peak < initial_peak


def test_dynamic_range_agc_limiting():
    afe = AcousticFrontEnd(target_peak=0.85)
    # Quiet speech
    quiet = np.random.normal(0, 0.02, 1600).astype(np.float32)
    boosted = afe.apply_dynamic_range_agc(quiet)
    peak = np.max(np.abs(boosted))
    assert 0.7 <= peak <= 0.86


def test_vad_boundary_padding():
    afe = AcousticFrontEnd(sample_rate=16000)
    audio = np.ones(1600, dtype=np.float32) * 0.5
    padded = afe.pad_vad_boundaries(audio, pre_padding_ms=100, hangover_ms=200)
    expected_len = 1600 + int(16000 * 0.1) + int(16000 * 0.2)
    assert len(padded) == expected_len
    # Verify beginning and end are zeros
    assert padded[0] == 0.0
    assert padded[-1] == 0.0


def test_full_front_end_pipeline():
    afe = AcousticFrontEnd()
    audio = np.random.normal(0, 0.05, 16000).astype(np.float32)
    processed = afe.process(audio)
    assert len(processed) == 16000
    assert processed.dtype == np.float32
    assert np.max(np.abs(processed)) <= 0.86
