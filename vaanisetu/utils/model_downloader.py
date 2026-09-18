"""
Model Downloader Utility — Programmatic access to download and check VaaniSetu models.
"""

from pathlib import Path
from typing import Dict
from scripts.download_models import download_model, MODELS, PROJECT_ROOT


def check_models_installed() -> Dict[str, bool]:
    """Check if required models are present locally."""
    status = {}
    for key, model in MODELS.items():
        target = model["target_dir"] / model["extracted_name"]
        status[key] = target.exists()
    return status


def ensure_models_downloaded() -> bool:
    """Ensure all models are downloaded, fetching any missing ones."""
    all_ok = True
    for key in MODELS:
        if not download_model(key):
            all_ok = False
    return all_ok
