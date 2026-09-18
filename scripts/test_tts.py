#!/usr/bin/env python3
"""
TTS Test Script — Test the Text-to-Speech engine.

Usage:
    # Synthesize text to file
    python scripts/test_tts.py --text "Hello from VaaniSetu"

    # Synthesize and play through speakers
    python scripts/test_tts.py --text "Hello" --play

    # Run all demo sentences
    python scripts/test_tts.py
"""

import sys
import os
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vaanisetu.tts import SherpaTTSEngine


DEMO_SENTENCES = [
    "Hello, welcome to VaaniSetu.",
    "This is a fully offline text to speech system.",
    "It runs on the lowest end phones without any internet connection.",
    "VaaniSetu means voice bridge, connecting people through speech.",
]


def test_synthesis(engine: SherpaTTSEngine, text: str, output_path: str, play: bool = False) -> None:
    """Test speech synthesis for a single sentence."""
    print(f"\n{'='*60}")
    print(f"📝 Text: \"{text}\"")
    print(f"{'='*60}")

    start = time.perf_counter()
    audio = engine.synthesize(text, output_path=output_path)
    elapsed = time.perf_counter() - start

    duration = len(audio) / engine.sample_rate if len(audio) > 0 else 0
    print(f"⏱️  Synthesis time: {elapsed:.2f}s for {duration:.1f}s audio")

    if play and len(audio) > 0:
        print("🔊 Playing...")
        from vaanisetu.tts.audio_utils import play_audio
        play_audio(audio, engine.sample_rate)
        print("✅ Playback complete.")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="VaaniSetu TTS Test")
    parser.add_argument("--text", type=str, help="Text to synthesize")
    parser.add_argument("--output", type=str, default="tts_output.wav", help="Output WAV path")
    parser.add_argument("--play", action="store_true", help="Play audio through speakers")
    parser.add_argument("--speed", type=float, default=1.0, help="Speaking speed")
    parser.add_argument("--model-dir", type=str, help="Custom model directory")
    args = parser.parse_args()

    # Initialize engine
    print("🚀 Initializing VaaniSetu TTS Engine...")
    engine = SherpaTTSEngine(model_dir=args.model_dir) if args.model_dir else SherpaTTSEngine()

    if args.text:
        test_synthesis(engine, args.text, args.output, play=args.play)
    else:
        # Run all demo sentences
        print(f"\n🎯 Running {len(DEMO_SENTENCES)} demo sentences...\n")
        output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        for i, sentence in enumerate(DEMO_SENTENCES, 1):
            output_path = os.path.join(output_dir, f"tts_demo_{i}.wav")
            test_synthesis(engine, sentence, output_path, play=args.play)

        print(f"✅ All {len(DEMO_SENTENCES)} sentences synthesized successfully!")


if __name__ == "__main__":
    main()
