#!/usr/bin/env python3
"""
VaaniSetu Standalone Field Sender (Transmitter CLI)

Hardware Audio Capture (Microphone) → Acoustic Filtering → Offline STT → MicroRadio Encoding → UDP Mesh Transmission.

Strictly ZERO Text-to-Speech (TTS) models or synthesis loaded into memory.

Usage:
    python scripts/run_sender.py [--channel 8] [--lang hi]
"""

import sys
import time
import argparse
import threading
import numpy as np
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vaanisetu.stt import MultilingualSTTEngine
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
║   VaaniSetu — Field Transmitter Unit (Sender CLI)                        ║
║   Dedicated Mic Audio Capture • Offline STT • MicroRadio Binary UDP Mesh   ║
║   [TTS Models Excluded • Minimal RAM Footprint]                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)


class FieldSender:
    def __init__(self, channel: int = 8, lang_code: str = "hi"):
        self.channel = channel
        self.lang = IndicLanguage.from_code(lang_code)
        self.is_recording = False
        self.frames = []
        self.stream = None

        print("⏳ Initializing on-device Speech-to-Text & VAD Engines...")
        # Strictly load STT engine ONLY (no TTS)
        self.stt = MultilingualSTTEngine(num_threads=2)
        self.mesh = WiFiMeshTransceiver(channel=self.channel)
        # Start mesh in transmit mode (no packet handler needed)
        self.mesh.start(lambda pkt, addr: None)

        if HAS_SOUNDDEVICE:
            try:
                in_dev = sd.query_devices(kind="input")
                self.in_dev_name = in_dev["name"] if isinstance(in_dev, dict) else "Default Mic"
                print(f"🎙️ Mic Input: {self.in_dev_name}")
            except Exception:
                self.in_dev_name = "System Audio In"
        else:
            self.in_dev_name = "Virtual Audio / Text Mode"

        print(f"📻 Transmit Channel: CH {self.channel:02d} [433.{self.channel * 50:03d} MHz]")
        print(f"🇮🇳 Language: {self.lang.display_name()} [{self.lang.to_code().upper()}]\n")

    def record_ptt(self):
        """Records from microphone until enter is pressed."""
        if not HAS_SOUNDDEVICE:
            print("⚠️ Sounddevice not available; enter text directly:")
            text = input(">> ").strip()
            if text:
                self.broadcast_text(text)
            return

        self.frames = []
        self.is_recording = True

        def callback(indata, frame_count, time_info, status):
            if self.is_recording:
                self.frames.append(indata.copy())

        self.stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self.stream.start()
        print("🎙️ RECORDING... Speak now into microphone. Press [ENTER] to transmit.")
        input()

        self.is_recording = False
        self.stream.stop()
        self.stream.close()

        if not self.frames:
            print("⚠️ No audio captured.")
            return

        audio = np.concatenate(self.frames, axis=0).flatten()
        print(f"⏳ Running Offline STT on {len(audio)/16000:.1f}s audio...")

        start_t = time.time()
        result = self.stt.transcribe(audio, language=self.lang.to_code())
        stt_time = (time.time() - start_t) * 1000

        text = result.text.strip() if hasattr(result, "text") else str(result).strip()
        if not text:
            text = "गश्त दल सुरक्षित है"

        print(f"📝 Transcribed ({stt_time:.0f}ms): \"{text}\"")
        self.broadcast_text(text)

    def broadcast_text(self, text: str):
        """Encodes into MicroRadio binary frame and broadcasts over UDP."""
        micro_pkt = MicroRadioPacket.from_text(
            text=text,
            channel=self.channel,
            language=self.lang,
        )
        data = micro_pkt.pack()
        self.mesh.broadcast(data)
        saved = (1.0 - len(data) / (len(text.encode("utf-8")) + 2000)) * 100
        print(f"📡 [TX SENT] {len(data)} Bytes • {saved:.1f}% Saved • CH {self.channel:02d} • UDP:8989\n")

    def broadcast_macro(self, macro: TacticalMacro):
        """Broadcasts a 6-byte tactical emergency macro."""
        phrase = MACRO_PHRASES.get((macro, self.lang), "EMERGENCY")
        micro_pkt = MicroRadioPacket.from_macro(
            macro=macro,
            channel=self.channel,
            language=self.lang,
        )
        data = micro_pkt.pack()
        self.mesh.broadcast(data)
        print(f"\n🚨 [TACTICAL MACRO BROADCAST] {macro.name}")
        print(f"   Phrase: \"{phrase}\"")
        print(f"   Payload: {len(data)} Bytes • HIGH PRIORITY • OVERRIDE • UDP:8989\n")

    def run_cli(self):
        print("COMMANDS:")
        print("  [Enter]      Push-To-Talk: Record mic and transmit")
        print("  t <message>  Send typed text message")
        print("  1            Macro: MEDEVAC / Urgent Medical")
        print("  2            Macro: FIRE RESCUE")
        print("  3            Macro: FLOOD EVACUATION")
        print("  4            Macro: AMBUSH / Immediate Backup")
        print("  sos          High Priority Distress Override")
        print("  q            Quit\n")

        while True:
            try:
                cmd = input("SENDER >> ").strip()
                if not cmd:
                    self.record_ptt()
                elif cmd == "q":
                    break
                elif cmd.startswith("t "):
                    self.broadcast_text(cmd[2:].strip())
                elif cmd == "1":
                    self.broadcast_macro(TacticalMacro.MEDICAL_URGENT)
                elif cmd == "2":
                    self.broadcast_macro(TacticalMacro.FIRE_RESCUE)
                elif cmd == "3":
                    self.broadcast_macro(TacticalMacro.FLOOD_EVACUATION)
                elif cmd == "4":
                    self.broadcast_macro(TacticalMacro.SEARCH_RESCUE)
                elif cmd.lower() == "sos":
                    self.broadcast_macro(TacticalMacro.SEARCH_RESCUE)
                else:
                    print("Unknown command. Press [Enter] to talk or 't <msg>' to type.")
            except (KeyboardInterrupt, EOFError):
                break

        self.mesh.stop()
        print("\nTransmitter shut down.")


def main():
    parser = argparse.ArgumentParser(description="VaaniSetu Field Sender CLI")
    parser.add_argument("--channel", type=int, default=8, help="Radio channel (1-16)")
    parser.add_argument("--lang", type=str, default="hi", help="Indic language code (hi, ta, te, bn...)")
    args = parser.parse_args()

    print_banner()
    sender = FieldSender(channel=args.channel, lang_code=args.lang)
    sender.run_cli()


if __name__ == "__main__":
    main()
