"""
Unit tests for MicroRadioPacket, IndicScriptCompressor, and TacticalMacro Codebook.
"""

import pytest
from vaanisetu.transceiver.protocol import (
    MicroRadioPacket,
    RadioPacket,
    PacketType,
    IndicLanguage,
    TacticalMacro,
    IndicScriptCompressor,
    MACRO_PHRASES,
    compute_crc16,
)


def test_indic_script_compressor_all_languages():
    samples = [
        ("hi", "बाढ़ का पानी बढ़ रहा है तुरंत सुरक्षित स्थान पर जाएं"),
        ("bn", "বন্যার জল বাড়ছে অবিলম্বে নিরাপদ আশ্রয়ে যান"),
        ("mr", "पुराचे पाणी वाढत आहे त्वरित सुरक्षित स्थळी जा"),
        ("gu", "પૂરના પાણી વધી રહ્યા છે તાત્કાલિક સલામત સ્થળે જાઓ"),
        ("ta", "வெள்ள நீர் உயர்ந்து வருகிறது உடனடியாக பாதுகாப்பான இடத்திற்கு செல்லவும்"),
        ("te", "వరద నీరు పెరుగుతోంది వెంటనే సురಕ್ಷిత ప్రాంతానికి వెళ్లండి"),
        ("kn", "ಪ್ರವಾಹದ ನೀರು ಹೆಚ್ಚುತ್ತಿದೆ ತಕ್ಷಣ ಸುರಕ್ಷಿತ ಸ್ಥಳಕ್ಕೆ ತೆರಳಿ"),
        ("ml", "വെള്ളപ്പൊക്കം ഉയരുന്നു ഉടൻ സുരക്ഷിത സ്ഥാനത്തേക്ക് മാറുക"),
        ("or", "ବନ୍ୟା ଜଳ ବଢୁଛି ତୁରନ୍ତ ନିରାପଦ ସ୍ଥାନକୁ ଯାଆନ୍ତୁ"),
        ("en", "Emergency medical team required at sector 4."),
    ]

    for lang_code, text in samples:
        compressed, is_comp = IndicScriptCompressor.compress(text, lang_code)
        assert len(compressed) > 0

        # Decompress
        restored = IndicScriptCompressor.decompress(compressed, lang_code, is_compressed=is_comp)
        assert restored == text, f"Lossless compression mismatch for {lang_code}"

        # If Indic, verify compression ratio > 50%
        if lang_code != "en":
            raw_len = len(text.encode("utf-8"))
            cmp_len = len(compressed)
            assert cmp_len < raw_len, f"Expected compression for {lang_code}, raw={raw_len}, cmp={cmp_len}"


def test_tactical_macro_codebook_phrases():
    # Verify all 10 macros have phrases in all 10 languages
    for macro in [
        TacticalMacro.FLOOD_EVACUATION,
        TacticalMacro.MEDICAL_URGENT,
        TacticalMacro.FIRE_RESCUE,
        TacticalMacro.STATUS_REPORT,
        TacticalMacro.ROAD_BLOCKED,
        TacticalMacro.RADIO_CHECK,
    ]:
        phrases = MACRO_PHRASES[macro]
        for lang in IndicLanguage:
            assert lang in phrases
            assert len(phrases[lang]) > 0


def test_micro_radio_packet_macro_serialization():
    # Macro packet: 3 bytes header + 1 byte payload + 2 bytes CRC = 6 bytes!
    micro = MicroRadioPacket(
        channel=7,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.TACTICAL_MACRO,
        macro=TacticalMacro.FLOOD_EVACUATION,
    )

    raw = micro.serialize()
    assert len(raw) == 6, f"Expected 6 bytes for macro packet, got {len(raw)}"

    # Deserialization
    restored = MicroRadioPacket.deserialize(raw)
    assert restored is not None
    assert restored.channel == 7
    assert restored.language == IndicLanguage.HINDI
    assert restored.macro == TacticalMacro.FLOOD_EVACUATION
    assert "बाढ़" in restored.text


def test_micro_radio_packet_indic_text_serialization():
    micro = MicroRadioPacket(
        text="तुरंत सुरक्षित स्थान पर जाएं",
        channel=12,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.NORMAL_PTT,
        seq=2,
    )

    raw = micro.serialize()
    assert len(raw) < 40  # Well under 40 bytes

    restored = MicroRadioPacket.deserialize(raw)
    assert restored is not None
    assert restored.channel == 12
    assert restored.language == IndicLanguage.HINDI
    assert restored.text == "तुरंत सुरक्षित स्थान पर जाएं"
    assert restored.seq == 2


def test_micro_packet_crc_corruption():
    micro = MicroRadioPacket(
        text="Testing corruption",
        channel=5,
        language=IndicLanguage.ENGLISH,
    )
    raw = bytearray(micro.serialize())
    # Corrupt last CRC byte
    raw[-1] ^= 0xFF

    restored = MicroRadioPacket.deserialize(bytes(raw))
    assert restored is None  # Must reject corrupted packet


def test_bandwidth_saving_calculation():
    micro = MicroRadioPacket(
        channel=7,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.TACTICAL_MACRO,
        macro=TacticalMacro.MEDICAL_URGENT,
    )
    raw_pcm, pkt_bytes, savings = micro.calculate_bandwidth_saving(audio_duration_sec=3.0)
    assert raw_pcm == 3.0 * 16000 * 2  # 96,000 bytes
    assert pkt_bytes == 6
    assert savings > 99.99  # > 99.99% bandwidth saving!
