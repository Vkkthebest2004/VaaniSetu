#!/usr/bin/env python3
"""
Model Downloader — Download STT, VAD, and TTS models for VaaniSetu.

Supports selective downloading by target application:
    python scripts/download_models.py --target sender    # Only STT and VAD models
    python scripts/download_models.py --target receiver  # Only TTS models
    python scripts/download_models.py --target all       # All models
"""

import os
import sys
import tarfile
import urllib.request
import shutil
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Model registry — URL, target directory, and description
MODELS = {
    "stt": {
        "name": "Zipformer-small English (int8)",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-zipformer-small-en-2023-06-26.tar.bz2",
        "target_dir": PROJECT_ROOT / "models" / "stt",
        "extracted_name": "sherpa-onnx-zipformer-small-en-2023-06-26",
        "size_mb": 107,
        "app": "sender",
    },
    "tts": {
        "name": "Piper VITS en_US-lessac-low",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-lessac-low.tar.bz2",
        "target_dir": PROJECT_ROOT / "models" / "tts",
        "extracted_name": "vits-piper-en_US-lessac-low",
        "size_mb": 64,
        "app": "receiver",
    },
    "vad": {
        "name": "Silero VAD (ONNX)",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        "target_dir": PROJECT_ROOT / "models" / "vad",
        "extracted_name": "silero_vad.onnx",
        "size_mb": 1,
        "is_direct_file": True,
        "app": "sender",
    },
}


def download_file(url: str, dest_path: Path) -> None:
    """Download a file with progress display."""
    print(f"  ⬇️  Downloading from {url}")

    def progress_hook(block_count, block_size, total_size):
        downloaded = block_count * block_size
        if total_size > 0:
            percent = min(100, downloaded * 100 // total_size)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  📦 {mb_downloaded:.1f}/{mb_total:.1f} MB ({percent}%)", end="", flush=True)

    urllib.request.urlretrieve(url, str(dest_path), reporthook=progress_hook)
    print()  # Newline after progress


def extract_tar_bz2(archive_path: Path, dest_dir: Path) -> None:
    """Extract a .tar.bz2 archive."""
    print(f"  📂 Extracting to {dest_dir}")
    with tarfile.open(str(archive_path), "r:bz2") as tar:
        tar.extractall(path=str(dest_dir))


def download_model(model_key: str) -> bool:
    """Download and extract a single model."""
    model = MODELS[model_key]
    target = model["target_dir"] / model["extracted_name"]

    if target.exists():
        print(f"  ✅ Already exists: {target}")
        return True

    print(f"\n📥 Downloading {model['name']} (~{model['size_mb']} MB)...")

    # Create target directory
    model["target_dir"].mkdir(parents=True, exist_ok=True)

    # Download
    archive_name = model["url"].split("/")[-1]
    archive_path = model["target_dir"] / archive_name

    try:
        if model.get("is_direct_file"):
            download_file(model["url"], target)
            print(f"  ✅ Successfully downloaded: {target}")
            return True
        else:
            download_file(model["url"], archive_path)
            extract_tar_bz2(archive_path, model["target_dir"])

            # Clean up archive
            archive_path.unlink()

            if target.exists():
                print(f"  ✅ Successfully installed: {target}")
                return True
            else:
                print(f"  ❌ Extraction failed — directory not found: {target}")
                return False

    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        if archive_path.exists():
            archive_path.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="VaaniSetu Model Downloader")
    parser.add_argument(
        "--target",
        choices=["all", "sender", "receiver"],
        default="all",
        help="Download models for specific target application (default: all)"
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="Optional explicit model keys to download (e.g. stt, tts, vad)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  VaaniSetu — Model Downloader")
    print(f"  Target: {args.target.upper()}")
    print("=" * 60)

    if args.models:
        models_to_download = args.models
    elif args.target == "sender":
        models_to_download = ["stt", "vad"]
        print("  🎯 Selected Sender models: Speech-to-Text (STT) + VAD (TTS excluded)")
    elif args.target == "receiver":
        models_to_download = ["tts"]
        print("  🎯 Selected Receiver models: Neural Text-to-Speech (TTS) (STT/VAD excluded)")
    else:
        models_to_download = list(MODELS.keys())

    results = {}
    for key in models_to_download:
        if key not in MODELS:
            print(f"⚠️  Unknown model key: {key}. Available: {', '.join(MODELS.keys())}")
            continue
        results[key] = download_model(key)

    # Summary
    print(f"\n{'='*60}")
    print("  Download Summary")
    print(f"{'='*60}")
    for key, success in results.items():
        status = "✅ Ready" if success else "❌ Failed"
        print(f"  [{MODELS[key]['app'].upper()}] {MODELS[key]['name']}: {status}")
    print(f"{'='*60}")

    if all(results.values()):
        print("\n🎉 All requested models ready! VaaniSetu can run fully offline.")
        return 0
    else:
        print("\n⚠️  Some downloads failed. Check your internet connection and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
