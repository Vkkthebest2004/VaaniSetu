"""
Unit tests for iTantra Neural Transceiver Protocol, Indic TTS & Multilingual Engine
"""

import pytest
import numpy as np
from vaanisetu.transceiver.protocol import RadioPacket, PacketType, IndicLanguage, compute_crc16
from vaanisetu.tts.indic_tts import IndicTTSEngine


def test_packet_serialization_deserialization():
    pkt = RadioPacket(
        text="बाढ़ का पानी बढ़ रहा है तुरंत सुरक्षित स्थान पर जाएं",
        channel=7,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.EMERGENCY_ALERT,
        seq=101,
    )
    raw = pkt.serialize()
    assert len(raw) > 0

    parsed = RadioPacket.deserialize(raw)
    assert parsed is not None
    assert parsed.text == pkt.text
    assert parsed.channel == 7
    assert parsed.language == IndicLanguage.HINDI
    assert parsed.packet_type == PacketType.EMERGENCY_ALERT
    assert parsed.is_emergency is True
    assert parsed.seq == 101


def test_crc16_corrupted_packet():
    pkt = RadioPacket(
        text="All units report in",
        channel=2,
        language=IndicLanguage.ENGLISH,
        packet_type=PacketType.NORMAL_PTT,
    )
    raw = bytearray(pkt.serialize())
    # Corrupt a byte
    raw[14] ^= 0xFF

    parsed = RadioPacket.deserialize(bytes(raw))
    assert parsed is None  # Should be rejected due to CRC mismatch


def test_all_10_indic_languages():
    langs = [
        ("hi", IndicLanguage.HINDI),
        ("en", IndicLanguage.ENGLISH),
        ("bn", IndicLanguage.BENGALI),
        ("te", IndicLanguage.TELUGU),
        ("mr", IndicLanguage.MARATHI),
        ("ta", IndicLanguage.TAMIL),
        ("gu", IndicLanguage.GUJARATI),
        ("kn", IndicLanguage.KANNADA),
        ("ml", IndicLanguage.MALAYALAM),
        ("or", IndicLanguage.ODIA),
    ]
    for code, expected_enum in langs:
        enum_val = IndicLanguage.from_code(code)
        assert enum_val == expected_enum
        assert enum_val.to_code() == code
        assert len(enum_val.display_name()) > 0


def test_bandwidth_saving_calculation():
    pkt = RadioPacket(
        text="Evacuate south sector immediately",
        channel=1,
        language=IndicLanguage.ENGLISH,
        packet_type=PacketType.EMERGENCY_ALERT,
    )
    raw_pcm, pkt_bytes, saving = pkt.calculate_bandwidth_saving(audio_duration_sec=3.0)
    assert raw_pcm == 96000  # 3s * 16000 * 2
    assert pkt_bytes < 100
    assert saving > 99.8  # > 99.8% bandwidth saved


def test_emergency_siren_generation():
    tts = IndicTTSEngine()
    siren = tts.generate_siren_chime(duration_sec=0.3)
    assert isinstance(siren, np.ndarray)
    assert len(siren) == int(tts.sample_rate * 0.3)
    assert np.max(np.abs(siren)) > 0.5
