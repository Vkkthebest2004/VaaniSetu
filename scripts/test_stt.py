#!/usr/bin/env python3
"""
STT Test Script — Test the Speech-to-Text engine.

Usage:
    # Transcribe a file
    python scripts/test_stt.py --audio path/to/audio.wav

    # Transcribe the bundled test audio
    python scripts/test_stt.py

    # Stream from microphone
    python scripts/test_stt.py --mic
"""

import sys
import os
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vaanisetu.stt import SherpaSTTEngine


def test_file_transcription(engine: SherpaSTTEngine, audio_path: str) -> None:
    """Test transcription from an audio file."""
    print(f"\n{'='*60}")
    print(f"🎧 Transcribing: {audio_path}")
    print(f"{'='*60}")

    start = time.perf_counter()
    text = engine.transcribe(audio_path)
    elapsed = time.perf_counter() - start

    print(f"\n📝 Result: \"{text}\"")
    print(f"⏱️  Total time: {elapsed:.2f}s")
    print(f"{'='*60}\n")

    return text


def test_mic_streaming(engine: SherpaSTTEngine) -> None:
    """Test real-time microphone streaming."""
    print(f"\n{'='*60}")
    print(f"🎤 Real-time Microphone Transcription")
    print(f"   Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    for text in engine.stream_from_mic():
        print(f"  📝 {text}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="VaaniSetu STT Test")
    parser.add_argument("--audio", type=str, help="Path to audio file to transcribe")
    parser.add_argument("--mic", action="store_true", help="Stream from microphone")
    parser.add_argument("--model-dir", type=str, help="Custom model directory")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD")
    args = parser.parse_args()

    # Initialize engine
    print("🚀 Initializing VaaniSetu STT Engine...")
    engine = SherpaSTTEngine(model_dir=args.model_dir) if args.model_dir else SherpaSTTEngine()

    if args.mic:
        test_mic_streaming(engine)
    elif args.audio:
        test_file_transcription(engine, args.audio)
    else:
        # Use bundled test audio
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        test_wavs_dir = os.path.join(
            project_root,
            "models", "stt", "sherpa-onnx-zipformer-small-en-2023-06-26", "test_wavs"
        )

        if os.path.isdir(test_wavs_dir):
            wav_files = sorted([f for f in os.listdir(test_wavs_dir) if f.endswith(".wav")])
            if wav_files:
                print(f"📂 Found {len(wav_files)} test audio file(s)")
                for wav_file in wav_files:
                    audio_path = os.path.join(test_wavs_dir, wav_file)
                    test_file_transcription(engine, audio_path)
            else:
                print("⚠️  No test WAV files found. Use --audio or --mic flags.")
        else:
            print("⚠️  No test audio directory found. Use --audio or --mic flags.")
            print(f"   Expected: {test_wavs_dir}")


if __name__ == "__main__":
    main()
