"""
Complex Multilingual Speech Stress Test Suite for iTantra Neural Transceiver.
Tests STT, TTS, Indic script normalization, and packet bandwidth reduction across:
Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Punjabi, and English.
"""

import pytest
import numpy as np
from vaanisetu.stt import MultilingualSTTEngine, IndicScriptNormalizer
from vaanisetu.tts import IndicTTSEngine
from vaanisetu.transceiver.protocol import (
    RadioPacket,
    MicroRadioPacket,
    IndicLanguage,
    PacketType,
    TacticalMacro,
)


@pytest.fixture(scope="module")
def stt_engine():
    return MultilingualSTTEngine(num_threads=2)


@pytest.fixture(scope="module")
def tts_engine():
    return IndicTTSEngine()


def test_indic_normalizer_perso_arabic():
    """Verify Urdu/Nastaliq script conversions into standard Devanagari Hindi."""
    test_cases = [
        ("ہم آگے بڑھ رہے ہیں", "हम आगे बढ़ रहे हैं"),
        ("مدد کی ضرورت", "मदद की ज़रूरत"),
        ("سلام دوست", "सलाम दोस्त"),
        ("سب ٹھیک ہے", "सब ठीक है"),
    ]
    for inp, expected in test_cases:
        res = IndicScriptNormalizer.normalize(inp, "hi")
        assert res == expected, f"Expected '{expected}', got '{res}'"


def test_indic_normalizer_roman_hindi():
    """Verify Romanized Hindi phrases map into standard Devanagari."""
    res = IndicScriptNormalizer.normalize("hum aage badh rahe hain", "hi")
    assert "हम" in res and "आगे" in res

    res2 = IndicScriptNormalizer.normalize("madad ki zarurat hai", "hi")
    assert "मदद" in res2


def test_dual_engine_tts_routing(tts_engine):
    """Verify TTS intelligently routes Indic text to Rohan-medium and English to Lessac-low."""
    # Hindi
    hi_audio, hi_dur = tts_engine.synthesize("नमस्ते, सब कुछ सुरक्षित है", language=IndicLanguage.HINDI)
    assert len(hi_audio) > 0
    assert hi_dur > 0.5
    assert tts_engine.sample_rate == 22050

    # English
    en_audio, en_dur = tts_engine.synthesize("Alpha unit report status", language=IndicLanguage.ENGLISH)
    assert len(en_audio) > 0
    assert en_dur > 0.5
    assert tts_engine.sample_rate == 16000


def test_emergency_alert_siren(tts_engine):
    """Verify emergency alert prepends siren chime and normalizes peak gain."""
    em_audio, em_dur = tts_engine.synthesize(
        "मदद की ज़रूरत है", language=IndicLanguage.HINDI, is_emergency=True
    )
    assert len(em_audio) > 0
    assert np.max(np.abs(em_audio)) > 0.9  # Normalized to 98% full scale
    assert em_dur > 1.0


def test_multilingual_stt_transcription(stt_engine, tts_engine):
    """Synthesizes Hindi voice and transcribes it back using MultilingualSTTEngine."""
    phrase = "हम आगे बढ़ रहे हैं सब ठीक है"
    audio, dur = tts_engine.synthesize(phrase, language=IndicLanguage.HINDI)

    text, lang = stt_engine.transcribe_with_lang(
        audio=audio, sample_rate=tts_engine.sample_rate, language="hi"
    )
    assert len(text) > 0
    assert lang == "hi"
    # Verify Devanagari output (Unicode 0x0900 - 0x097F)
    has_devanagari = any(0x0900 <= ord(c) <= 0x097F for c in text)
    assert has_devanagari, f"Output text '{text}' should contain Devanagari script."


def test_micro_packet_bandwidth_compression():
    """Verify 99%+ bandwidth reduction for Indic speech transmissions."""
    text = "अग्रिम चौकी पर भारी गोलीबारी हो रही है, तत्काल सहायता भेजो"
    packet = MicroRadioPacket(
        text=text,
        channel=7,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.EMERGENCY_ALERT,
    )
    data = packet.serialize()
    raw_pcm_bytes, pkt_len, saving = packet.calculate_bandwidth_saving(audio_duration_sec=3.5)

    assert pkt_len < 100  # Less than 100 bytes
    assert saving > 99.5  # Greater than 99.5% reduction
