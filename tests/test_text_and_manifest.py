"""
Tests for IndicTextNormalizer and ManifestBuilder (Speaker-Disjoint & Balancing).
"""

import os
import tempfile
import pytest
from audio.preprocessing.text_normalizer import IndicTextNormalizer
from datasets.manifest_builder import ManifestBuilder


def test_indic_text_normalizer():
    norm = IndicTextNormalizer()

    # Hindi with artifact and danda
    raw_hi = "मुझे <cough> दिल्ली जाना है। १२३"
    _, clean_hi = norm.normalize(raw_hi, language="hi")
    assert clean_hi == "मुझे दिल्ली जाना है 123"

    # Punjabi Gurmukhi digits
    raw_pa = "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ੧੨੩"
    _, clean_pa = norm.normalize(raw_pa, language="pa")
    assert "123" in clean_pa

    # Tamil text
    raw_ta = "வணக்கம் [applause] ௧௨௩"
    _, clean_ta = norm.normalize(raw_ta, language="ta")
    assert "123" in clean_ta


def test_manifest_builder_speaker_disjoint_splitting():
    builder = ManifestBuilder()

    # Add samples from 5 speakers across Hindi and Tamil
    for spk_id in ["spk_01", "spk_02", "spk_03", "spk_04", "spk_05"]:
        for i in range(3):
            builder.add_record(
                audio_path=f"audio/hi/{spk_id}_{i}.wav",
                language="hi",
                speaker_id=spk_id,
                duration=3.0,
                sample_rate=16000,
                transcript_raw="परीक्षण वाक्य"
            )

    # Split
    splits = builder.split_speaker_disjoint(train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)

    train_spks = {r.speaker_id for r in splits["train"]}
    val_spks = {r.speaker_id for r in splits["validation"]}
    test_spks = {r.speaker_id for r in splits["test"]}

    # STRICT CHECK: ZERO SPEAKER LEAKAGE
    assert len(train_spks.intersection(val_spks)) == 0
    assert len(train_spks.intersection(test_spks)) == 0
    assert len(val_spks.intersection(test_spks)) == 0


def test_manifest_builder_temperature_balancing():
    builder = ManifestBuilder()

    # Add 100 Hindi samples and 10 Odia samples
    for i in range(100):
        builder.add_record(f"audio/hi/{i}.wav", "hi", f"spk_hi_{i}", 2.0, 16000, "परीक्षण")
    for i in range(10):
        builder.add_record(f"audio/or/{i}.wav", "or", f"spk_or_{i}", 2.0, 16000, "ପରୀକ୍ଷା")

    # Temperature sampling boosts lower-resource language weight
    weights = builder.get_temperature_weights(temperature=0.5)
    assert weights["hi"] > weights["or"]
    # With T=0.5, Odia relative probability is boosted significantly compared to naive 10:1 ratio
    assert weights["or"] > 0.05
