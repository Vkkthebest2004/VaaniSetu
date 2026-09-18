"""
iTantra ASR Evaluation Suite
Conforms to Sections 33, 34, 35, 71, and 72 of iTantra Technical Specification:
Computes:
- Word Error Rate (WER)
- Character Error Rate (CER)
- Real-Time Factor (RTF = processing time / audio duration)
- Error category logging: evaluation/errors.csv
- Multilingual ASR Report across 10 Indian languages
"""

import os
import csv
import time
from typing import List, Dict, Any, Tuple
from pathlib import Path
import numpy as np


class ASREvaluator:
    """
    Evaluates speech recognition performance across Indian languages.
    Computes Levenshtein edit distances for WER and CER, and tracks RTF.
    """

    LANGUAGES = [
        "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or"
    ]

    ERROR_LOG_COLUMNS = [
        "audio",
        "language",
        "reference",
        "prediction",
        "error_type",
        "speaker",
        "condition"
    ]

    def __init__(self, error_log_path: str = "evaluation/errors.csv"):
        self.error_log_path = Path(error_log_path)
        self.error_records: List[Dict[str, Any]] = []

    @staticmethod
    def compute_levenshtein(ref: List[str], hyp: List[str]) -> Tuple[int, int, int]:
        """
        Compute Levenshtein edit distance between reference and hypothesis tokens.
        Returns: (substitutions, deletions, insertions)
        """
        n = len(ref)
        m = len(hyp)
        dp = np.zeros((n + 1, m + 1), dtype=int)

        for i in range(n + 1):
            dp[i][0] = i
        for j in range(m + 1):
            dp[0][j] = j

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                if ref[i - 1] == hyp[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i - 1][j],      # deletion
                        dp[i][j - 1],      # insertion
                        dp[i - 1][j - 1]   # substitution
                    )

        # Backtrack to count S, D, I
        i, j = n, m
        s, d, ins = 0, 0, 0
        while i > 0 or j > 0:
            if i > 0 and j > 0 and ref[i - 1] == hyp[j - 1]:
                i -= 1
                j -= 1
            elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
                s += 1
                i -= 1
                j -= 1
            elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
                d += 1
                i -= 1
            elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
                ins += 1
                j -= 1
            else:
                break

        return s, d, ins

    def calculate_wer(self, reference: str, hypothesis: str) -> float:
        """Calculate Word Error Rate (WER)."""
        ref_words = reference.strip().split()
        hyp_words = hypothesis.strip().split()
        if not ref_words:
            return 0.0 if not hyp_words else 1.0

        s, d, i = self.compute_levenshtein(ref_words, hyp_words)
        return (s + d + i) / float(len(ref_words))

    def calculate_cer(self, reference: str, hypothesis: str) -> float:
        """Calculate Character Error Rate (CER)."""
        ref_chars = list(reference.replace(" ", ""))
        hyp_chars = list(hypothesis.replace(" ", ""))
        if not ref_chars:
            return 0.0 if not hyp_chars else 1.0

        s, d, i = self.compute_levenshtein(ref_chars, hyp_chars)
        return (s + d + i) / float(len(ref_chars))

    def calculate_rtf(self, processing_time_sec: float, audio_duration_sec: float) -> float:
        """
        Calculate Real-Time Factor (RTF).
        RTF = processing time / audio duration.
        RTF < 1.0 means faster than real-time.
        """
        if audio_duration_sec <= 0:
            return 0.0
        return round(processing_time_sec / audio_duration_sec, 4)

    def log_error(
        self,
        audio_path: str,
        language: str,
        reference: str,
        prediction: str,
        error_type: str = "substitution",
        speaker: str = "spk_001",
        condition: str = "clean"
    ):
        """Record an error instance into evaluation/errors.csv."""
        record = {
            "audio": audio_path,
            "language": language,
            "reference": reference,
            "prediction": prediction,
            "error_type": error_type,
            "speaker": speaker,
            "condition": condition
        }
        self.error_records.append(record)

    def save_errors_csv(self):
        """Write error log to disk."""
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.error_log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.ERROR_LOG_COLUMNS)
            writer.writeheader()
            for r in self.error_records:
                writer.writerow(r)
