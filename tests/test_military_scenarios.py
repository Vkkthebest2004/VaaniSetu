"""
Pytest integration for military-scale battlefield stress scenarios.
Validates:
- Cockpit rotorcraft drone attenuation at 0dB SNR
- Blast transient peak ceiling and soft limiter recovery
- Tactical electronic warfare (RF jamming, bit-flip detection, micro-packet survival)
- Tactical phonetic confusion rescoring & ITN
- High-stress barge-in preemption latency
"""

import pytest
import numpy as np
from benchmarks.military_stress_test import (
    BattlefieldAcousticSimulator,
    TacticalRFJammingSimulator
)
from vaanisetu.stt.acoustic_front_end import AcousticFrontEnd
from vaanisetu.stt.tactical_rescorer import TacticalRescorer
from vaanisetu.transceiver.protocol import MicroRadioPacket, TacticalMacro
from runtime.conversation.state_machine import iConversationEngine, ConversationState


def test_rotorcraft_drone_snr_attenuation():
    sim = BattlefieldAcousticSimulator()
    front_end = AcousticFrontEnd(sample_rate=16000)

    rotor_noise = sim.generate_rotorcraft_drone(duration_sec=1.5, rotor_freq=22.0)
    speech = np.sin(2 * np.pi * 400 * np.linspace(0, 1.5, int(16000 * 1.5))).astype(np.float32) * 0.3

    # 0 dB SNR mix
    mixed = sim.mix_at_snr(speech, rotor_noise, snr_db=0.0)

    # Process
    processed = front_end.process(mixed)
    assert processed.ndim == 1
    assert len(processed) == len(mixed)
    # Verify signal energy is retained without digital clipping
    assert np.max(np.abs(processed)) <= 0.90


def test_artillery_blast_limiting():
    sim = BattlefieldAcousticSimulator()
    front_end = AcousticFrontEnd(sample_rate=16000)

    blast = sim.generate_artillery_blast_transient(duration_sec=0.2)
    # Blast has initial peak > 2.0
    assert np.max(np.abs(blast)) > 2.0

    limited = front_end.process(blast)
    # Must be tamed below 0.90 by soft tanh AGC limiter
    assert np.max(np.abs(limited)) <= 0.90


def test_rf_jamming_crc_and_burst_survival():
    rf_sim = TacticalRFJammingSimulator(random_seed=42)

    # 6-byte emergency macro packet
    from vaanisetu.transceiver.protocol import IndicLanguage, PacketType
    pkt = MicroRadioPacket(
        channel=3,
        language=IndicLanguage.HINDI,
        packet_type=PacketType.TACTICAL_MACRO,
        macro=TacticalMacro.MEDICAL_URGENT,
        seq=1
    )
    packet = pkt.serialize()
    assert len(packet) == 6

    # Verify bit flip detection via CRC16
    corrupted_pkt = rf_sim.inject_bit_flips(packet, ber=0.1)
    # If bits were flipped, deserialization must reject it (returns None)
    if corrupted_pkt != packet:
        assert MicroRadioPacket.deserialize(corrupted_pkt) is None

    # Verify redundant burst survival through 40% packet drop
    burst = [packet] * 8
    delivered = rf_sim.simulate_burst_packet_loss(burst, drop_rate=0.40)
    assert len(delivered) > 0  # At least 1 copy arrived intact


def test_tactical_rescorer_fixes_confusions():
    rescorer = TacticalRescorer()

    raw_input = "URGENT OF ACCUATION SQUAD TO SECTOR 4"
    rescored = rescorer.rescore(raw_input)
    assert rescored == "URGENT EVACUATION SQUAD TO Sector 04"

    raw_ch = "RADIO CHANNEL 7 CALL SIGN BRAVO MATE TEAM"
    rescored_ch = rescorer.rescore(raw_ch)
    assert rescored_ch == "RADIO Channel 07 CALL SIGN BRAVO MEDICAL TEAM"


def test_barge_in_preemption_latency():
    convo = iConversationEngine()
    convo._set_state(ConversationState.RESPONDING)
    convo.vad._using_sherpa = False  # Direct energy test

    countermand_chunk = np.ones(512, dtype=np.float32) * 0.35
    res = convo.process_incoming_audio_chunk(countermand_chunk)

    assert res["action"] == "barge_in_triggered"
    assert convo.current_state == ConversationState.LISTENING
