#!/usr/bin/env python3
"""
Model Downloader — Download STT and TTS models for VaaniSetu.

Run this once to download all required models:
    python scripts/download_models.py

This requires internet access (one-time only).
After downloading, VaaniSetu runs fully offline.
"""

import os
import sys
import tarfile
import urllib.request
import shutil
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
    },
    "tts": {
        "name": "Piper VITS en_US-lessac-low",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-lessac-low.tar.bz2",
        "target_dir": PROJECT_ROOT / "models" / "tts",
        "extracted_name": "vits-piper-en_US-lessac-low",
        "size_mb": 64,
    },
    "vad": {
        "name": "Silero VAD (ONNX)",
        "url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
        "target_dir": PROJECT_ROOT / "models" / "vad",
        "extracted_name": "silero_vad.onnx",
        "size_mb": 1,
        "is_direct_file": True,
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
    print("=" * 60)
    print("  VaaniSetu — Model Downloader")
    print("  This requires internet access (one-time only)")
    print("=" * 60)

    # Parse optional arguments
    models_to_download = sys.argv[1:] if len(sys.argv) > 1 else list(MODELS.keys())

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
        print(f"  {MODELS[key]['name']}: {status}")
    print(f"{'='*60}")

    if all(results.values()):
        print("\n🎉 All models ready! VaaniSetu can now run fully offline.")
        return 0
    else:
        print("\n⚠️  Some downloads failed. Check your internet connection and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
