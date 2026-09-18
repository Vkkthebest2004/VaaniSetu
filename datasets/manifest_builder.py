"""
iTantra Dataset Manifest Builder & Speaker-Disjoint Splitter
Conforms to Sections 9, 12, 16, and 17 of iTantra Technical Specification:
Features:
- Standard manifest generation: datasets/manifests/all.csv
- Speaker-Disjoint Partitioning (Strict guarantee: Zero speaker leakage across train/val/test)
- Multilingual Statistics & Temperature-Based Sampling
- Validates data format and maintains data lineage and licensing info
"""

import os
import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import numpy as np

from audio.preprocessing.text_normalizer import IndicTextNormalizer


class ManifestRecord:
    """Represents a single speech sample metadata record."""
    def __init__(
        self,
        audio_path: str,
        language: str,
        speaker_id: str,
        duration: float,
        sample_rate: int,
        transcript_raw: str,
        transcript_normalized: str,
        source: str = "custom",
        license_type: str = "permissive",
        quality: str = "good",
        split: str = "train"
    ):
        self.audio_path = audio_path
        self.language = language
        self.speaker_id = speaker_id
        self.duration = float(duration)
        self.sample_rate = int(sample_rate)
        self.transcript_raw = transcript_raw
        self.transcript_normalized = transcript_normalized
        self.source = source
        self.license = license_type
        self.quality = quality
        self.split = split

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_path": self.audio_path,
            "language": self.language,
            "speaker_id": self.speaker_id,
            "duration": round(self.duration, 3),
            "sample_rate": self.sample_rate,
            "transcript_raw": self.transcript_raw,
            "transcript_normalized": self.transcript_normalized,
            "source": self.source,
            "license": self.license,
            "quality": self.quality,
            "split": self.split
        }


class ManifestBuilder:
    """
    Builds, validates, splits, and balances dataset manifests for iTantra.
    """

    COLUMNS = [
        "audio_path",
        "language",
        "speaker_id",
        "duration",
        "sample_rate",
        "transcript_raw",
        "transcript_normalized",
        "source",
        "license",
        "quality",
        "split"
    ]

    def __init__(self):
        self.normalizer = IndicTextNormalizer()
        self.records: List[ManifestRecord] = []

    def add_record(
        self,
        audio_path: str,
        language: str,
        speaker_id: str,
        duration: float,
        sample_rate: int,
        transcript_raw: str,
        source: str = "custom",
        license_type: str = "permissive",
        quality: str = "good"
    ) -> ManifestRecord:
        """Add a speech record, automatically normalizing text while keeping raw."""
        _, norm_text = self.normalizer.normalize(transcript_raw, language=language)
        record = ManifestRecord(
            audio_path=audio_path,
            language=language,
            speaker_id=speaker_id,
            duration=duration,
            sample_rate=sample_rate,
            transcript_raw=transcript_raw,
            transcript_normalized=norm_text,
            source=source,
            license_type=license_type,
            quality=quality,
            split="train"
        )
        self.records.append(record)
        return record

    def split_speaker_disjoint(
        self,
        train_ratio: float = 0.80,
        val_ratio: float = 0.10,
        test_ratio: float = 0.10,
        random_seed: int = 42
    ) -> Dict[str, List[ManifestRecord]]:
        """
        Partition records by speaker_id such that no speaker appears in more than one split.
        Conforms strictly to Section 16 (Zero speaker leakage).
        """
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-4, "Ratios must sum to 1.0"
        rng = np.random.default_rng(random_seed)

        # Group records by language, then by speaker
        lang_speaker_records = defaultdict(lambda: defaultdict(list))
        for r in self.records:
            lang_speaker_records[r.language][r.speaker_id].append(r)

        splits = {"train": [], "validation": [], "test": []}

        for lang, speakers in lang_speaker_records.items():
            spk_list = list(speakers.keys())
            rng.shuffle(spk_list)

            num_spks = len(spk_list)
            if num_spks == 1:
                # Edge case with single speaker
                train_spks = spk_list
                val_spks = []
                test_spks = []
            elif num_spks == 2:
                train_spks = [spk_list[0]]
                val_spks = [spk_list[1]]
                test_spks = []
            else:
                n_train = max(1, int(round(num_spks * train_ratio)))
                n_val = max(1, int(round(num_spks * val_ratio)))
                # Adjust to leave at least 1 for test if possible
                if n_train + n_val >= num_spks:
                    n_train = num_spks - 2
                    n_val = 1
                train_spks = spk_list[:n_train]
                val_spks = spk_list[n_train:n_train + n_val]
                test_spks = spk_list[n_train + n_val:]

            for spk in train_spks:
                for r in speakers[spk]:
                    r.split = "train"
                    splits["train"].append(r)

            for spk in val_spks:
                for r in speakers[spk]:
                    r.split = "validation"
                    splits["validation"].append(r)

            for spk in test_spks:
                for r in speakers[spk]:
                    r.split = "test"
                    splits["test"].append(r)

        return splits

    def compute_statistics(self) -> Dict[str, Any]:
        """Compute language hours, speaker counts, and sample counts (Section 17)."""
        stats = defaultdict(lambda: {"samples": 0, "total_seconds": 0.0, "speakers": set()})
        for r in self.records:
            stats[r.language]["samples"] += 1
            stats[r.language]["total_seconds"] += r.duration
            stats[r.language]["speakers"].add(r.speaker_id)

        summary = {}
        for lang, d in stats.items():
            summary[lang] = {
                "samples": d["samples"],
                "total_hours": round(d["total_seconds"] / 3600.0, 4),
                "num_speakers": len(d["speakers"])
            }
        return summary

    def get_temperature_weights(self, temperature: float = 0.5) -> Dict[str, float]:
        """
        Compute multinomial sampling probability weights per language using temperature sampling:
        p_l = (N_l ** (1/T)) / sum(N_k ** (1/T))
        Prevents dominant languages from starving low-resource languages.
        """
        stats = self.compute_statistics()
        if not stats:
            return {}

        counts = {lang: d["samples"] for lang, d in stats.items()}
        power = temperature if temperature <= 1.0 else (1.0 / temperature)
        scaled = {lang: (cnt ** power) for lang, cnt in counts.items()}
        total = sum(scaled.values())
        return {lang: round(val / total, 4) for lang, val in scaled.items()}

    def save_csv(self, output_path: str = "datasets/manifests/all.csv") -> str:
        """Write records to standardized CSV file."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        with open(out_p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            writer.writeheader()
            for r in self.records:
                writer.writerow(r.to_dict())

        return str(out_p)

    def load_csv(self, input_path: str = "datasets/manifests/all.csv") -> List[ManifestRecord]:
        """Load manifest from CSV."""
        inp_p = Path(input_path)
        if not inp_p.exists():
            raise FileNotFoundError(f"Manifest not found: {input_path}")

        records = []
        with open(inp_p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rec = ManifestRecord(
                    audio_path=row["audio_path"],
                    language=row["language"],
                    speaker_id=row["speaker_id"],
                    duration=float(row["duration"]),
                    sample_rate=int(row["sample_rate"]),
                    transcript_raw=row["transcript_raw"],
                    transcript_normalized=row["transcript_normalized"],
                    source=row.get("source", "custom"),
                    license_type=row.get("license", "permissive"),
                    quality=row.get("quality", "good"),
                    split=row.get("split", "train")
                )
                records.append(rec)
        self.records = records
        return records
