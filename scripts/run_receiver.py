#!/usr/bin/env python3
"""
VaaniSetu Standalone Command Listening Station (Receiver CLI)

UDP Mesh Socket Listener (Port 8989) → MicroRadio CRC-16 Verify → Indic Neural TTS → Speaker Playback.

Strictly ZERO Microphone Recording or Speech-to-Text (STT) models loaded into memory.

Usage:
    python scripts/run_receiver.py [--channel 8] [--auto-tts]
"""

import sys
import time
import argparse
import numpy as np
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vaanisetu.tts import IndicTTSEngine
from vaanisetu.transceiver.protocol import (
    RadioPacket,
    PacketType,
    IndicLanguage,
    MicroRadioPacket,
    TacticalMacro,
    MACRO_PHRASES,
)
from vaanisetu.transceiver.wifi_mesh import WiFiMeshTransceiver

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except Exception:
    HAS_SOUNDDEVICE = False


def print_banner():
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║   VaaniSetu — Command Listening Station (Receiver CLI)                   ║
║   UDP Mesh Socket Listener • Offline Neural TTS • Speaker Audio Playback  ║
║   [Microphone & STT Models Excluded • Zero Audio In Overhead]             ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)


class CommandStationReceiver:
    def __init__(self, channel: int = 8, auto_tts: bool = True):
        self.channel = channel
        self.auto_tts = auto_tts

        print("⏳ Initializing on-device Neural Text-to-Speech Engine...")
        # Strictly load TTS engine ONLY (no STT)
        self.tts = IndicTTSEngine()

        if HAS_SOUNDDEVICE:
            try:
                out_dev = sd.query_devices(kind="output")
                self.out_dev_name = out_dev["name"] if isinstance(out_dev, dict) else "Default Speaker"
                print(f"🔊 Speaker Output: {self.out_dev_name}")
            except Exception:
                self.out_dev_name = "System Audio Out"
        else:
            self.out_dev_name = "Virtual Output"

        print(f"📻 Station Channel: CH {self.channel:02d} [433.{self.channel * 50:03d} MHz]")
        print(f"🔊 Auto-TTS Readout: {'ENABLED' if self.auto_tts else 'MUTED'}\n")

        self.mesh = WiFiMeshTransceiver(channel=self.channel)
        self.mesh.start(self.on_packet_received)
        print("🟢 Command Station Listening on UDP port 8989... Press [Ctrl+C] to exit.\n")

    def on_packet_received(self, data, addr: tuple):
        """Called when a packet arrives over UDP mesh."""
        try:
            # Check if raw bytes or RadioPacket
            if isinstance(data, bytes):
                micro_pkt = MicroRadioPacket.unpack(data)
                is_emergency = micro_pkt.is_emergency
                text = micro_pkt.resolved_text
                channel = micro_pkt.channel
                lang = micro_pkt.language
                byte_len = len(data)
            else:
                is_emergency = (data.packet_type == PacketType.EMERGENCY_ALERT)
                text = data.text
                channel = data.channel
                lang = data.language
                byte_len = len(data.serialize())

            alert_tag = "🚨 [EMERGENCY DISTRESS OVERRIDE]" if is_emergency else "📡 [INCOMING TRANSMISSION]"
            print(f"\n{alert_tag} From {addr[0]}:{addr[1]} | CH {channel:02d} | {lang.display_name()}:")
            print(f"   \"{text}\" ({byte_len} Bytes • UDP:8989)")

            if self.auto_tts and HAS_SOUNDDEVICE:
                self.synthesize_and_play(text, lang, is_emergency)

        except Exception as e:
            print(f"⚠️ Packet decode error from {addr}: {e}")

    def synthesize_and_play(self, text: str, lang: IndicLanguage, is_emergency: bool):
        """Synthesizes text to speech with Indic TTS and plays through speaker."""
        try:
            start_t = time.time()
            audio, sr = self.tts.synthesize(
                text=text,
                language=lang,
                is_emergency=is_emergency,
            )
            synth_time = (time.time() - start_t) * 1000
            print(f"   🔊 Synthesized in {synth_time:.0f}ms ({len(audio)/sr:.1f}s audio) -> Speaker")
            sd.play(audio, samplerate=sr)
            sd.wait()
        except Exception as e:
            print(f"   ❌ TTS playback error: {e}")

    def run(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Command Station...")
            self.mesh.stop()


def main():
    parser = argparse.ArgumentParser(description="VaaniSetu Command Station Receiver CLI")
    parser.add_argument("--channel", type=int, default=8, help="Station channel to monitor (1-16)")
    parser.add_argument("--auto-tts", action="store_true", default=True, help="Automatically synthesize voice on packet arrival")
    parser.add_argument("--muted", dest="auto_tts", action="store_false", help="Mute TTS voice output (log only)")
    args = parser.parse_args()

    print_banner()
    station = CommandStationReceiver(channel=args.channel, auto_tts=args.auto_tts)
    station.run()


if __name__ == "__main__":
    main()
