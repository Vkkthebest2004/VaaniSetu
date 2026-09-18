#!/usr/bin/env python3
"""
Comprehensive Multilingual Accuracy Benchmark Suite for iTantra / VaaniSetu.

Evaluates STT accuracy, latency, and robustness across:
- All 10 Indian Languages (hi, bn, ta, te, mr, gu, kn, ml, pa, or) + English (en).
- 6 Acoustic Stress Conditions:
  1. Clean Native Baseline
  2. Cockpit Rotorcraft & Turbine Noise (0 dB SNR)
  3. Emergency G.711 Telephone Channel (300-3400Hz + 8-bit companding + line hiss)
  4. Artillery Overpressure Shockwave Transient
  5. Low-Amplitude Post-Blast Survivor Whisper (RMS < 0.01)
  6. Urgent Panic Cadence (1.25x tempo)

Computes:
- Word Error Rate (WER)
- Character Error Rate (CER)
- Real-Time Factor (RTF)
- Average End-to-End Latency (ms)
- Language Identification (LID) Precision
"""

import os
import sys
import csv
import json
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vaanisetu.stt.multilingual_whisper import MultilingualSTTEngine
from vaanisetu.stt.audio_utils import load_audio
from evaluation.asr.evaluator import ASREvaluator

MANIFEST_PATH = PROJECT_ROOT / "datasets" / "evaluation" / "manifest.csv"
REPORT_JSON_PATH = PROJECT_ROOT / "evaluation" / "benchmark_report.json"
REPORT_MD_PATH = PROJECT_ROOT / "evaluation" / "benchmark_report.md"


def normalize_text_for_eval(text: str) -> str:
    """Canonicalize text for fair acoustic evaluation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text.strip())
    # Strip basic punctuation
    for punct in [".", ",", "!", "?", "।", "-", ":", ";", '"', "'", "(", ")"]:
        text = text.replace(punct, " ")
    return " ".join(text.split()).strip()


def run_benchmark(sample_limit_per_lang: int = 18):
    """
    Executes the full automated multilingual benchmark.
    sample_limit_per_lang: evaluate up to N samples per language across conditions.
    """
    print("=" * 80)
    print("  🏆 iTANTRA MULTILINGUAL ACCURACY & TACTICAL STRESS BENCHMARK")
    print("=" * 80)

    if not MANIFEST_PATH.exists():
        print(f"❌ Manifest not found at {MANIFEST_PATH}. Run scripts/import_difficult_benchmark.py first.")
        return

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        manifest_rows = list(reader)

    print(f"📦 Loaded {len(manifest_rows)} benchmark scenarios from manifest.")
    engine = MultilingualSTTEngine(num_threads=2)
    evaluator = ASREvaluator()

    results_by_lang: Dict[str, Dict[str, Any]] = {}
    results_by_condition: Dict[str, Dict[str, Any]] = {}
    detailed_records = []

    # Language counters
    lang_counts: Dict[str, int] = {}

    for row_idx, row in enumerate(manifest_rows):
        lang = row["language"]
        cond = row["condition"]
        ref_raw = row["reference_text"]
        ref_norm = normalize_text_for_eval(ref_raw)
        audio_rel_path = row["audio_path"]
        audio_full_path = PROJECT_ROOT / audio_rel_path

        if not audio_full_path.exists():
            continue

        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts[lang] > sample_limit_per_lang:
            continue

        audio, sr = load_audio(str(audio_full_path), target_sr=16000)
        audio_dur = len(audio) / 16000.0

        t0 = time.perf_counter()
        # Evaluate STT with VAD and language targeting
        pred_text, detected_lang = engine.transcribe_with_lang(
            audio, sample_rate=16000, language=lang, use_vad=True
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        rtf = (latency_ms / 1000.0) / audio_dur if audio_dur > 0 else 0.0

        pred_norm = normalize_text_for_eval(pred_text)

        # Compute WER & CER
        wer = evaluator.calculate_wer(ref_norm, pred_norm)
        cer = evaluator.calculate_cer(ref_norm, pred_norm)

        # Cap WER to 1.0 for reporting sanity
        wer_capped = min(1.0, wer)
        cer_capped = min(1.0, cer)
        lid_match = (detected_lang == lang) or (lang in ("hi", "ur") and detected_lang in ("hi", "ur"))

        record = {
            "language": lang,
            "condition": cond,
            "category": row.get("category", ""),
            "duration_sec": audio_dur,
            "reference": ref_norm,
            "hypothesis": pred_norm,
            "detected_lang": detected_lang,
            "lid_match": lid_match,
            "wer": wer_capped,
            "cer": cer_capped,
            "latency_ms": latency_ms,
            "rtf": rtf,
        }
        detailed_records.append(record)

        # Aggregate by language
        if lang not in results_by_lang:
            results_by_lang[lang] = {
                "wers": [], "cers": [], "rtfs": [], "latencies": [], "lids": [], "count": 0
            }
        results_by_lang[lang]["wers"].append(wer_capped)
        results_by_lang[lang]["cers"].append(cer_capped)
        results_by_lang[lang]["rtfs"].append(rtf)
        results_by_lang[lang]["latencies"].append(latency_ms)
        results_by_lang[lang]["lids"].append(1.0 if lid_match else 0.0)
        results_by_lang[lang]["count"] += 1

        # Aggregate by condition
        if cond not in results_by_condition:
            results_by_condition[cond] = {
                "wers": [], "cers": [], "rtfs": [], "latencies": [], "count": 0
            }
        results_by_condition[cond]["wers"].append(wer_capped)
        results_by_condition[cond]["cers"].append(cer_capped)
        results_by_condition[cond]["rtfs"].append(rtf)
        results_by_condition[cond]["latencies"].append(latency_ms)
        results_by_condition[cond]["count"] += 1

        print(f"[{row_idx+1:03d}/{len(manifest_rows)}] {lang.upper()} ({cond:15s}) | CER: {cer_capped*100:4.1f}% | RTF: {rtf:4.2f} | Hyp: '{pred_norm[:35]}...'")

    # Generate Summary Tables
    print("\n" + "=" * 80)
    print("  📊 MULTILINGUAL BENCHMARK RESULTS ACROSS 10 INDIC LANGUAGES + ENGLISH")
    print("=" * 80)
    print(f"{'Language':12s} | {'Samples':7s} | {'Avg WER':8s} | {'Avg CER':8s} | {'Avg RTF':8s} | {'Avg Latency':11s} | {'LID Acc':7s}")
    print("-" * 80)

    lang_summary = {}
    for lang, data in sorted(results_by_lang.items()):
        avg_wer = np.mean(data["wers"]) * 100
        avg_cer = np.mean(data["cers"]) * 100
        avg_rtf = np.mean(data["rtfs"])
        avg_lat = np.mean(data["latencies"])
        lid_acc = np.mean(data["lids"]) * 100
        lang_summary[lang] = {
            "samples": data["count"],
            "wer_pct": round(avg_wer, 1),
            "cer_pct": round(avg_cer, 1),
            "rtf": round(avg_rtf, 3),
            "latency_ms": round(avg_lat, 1),
            "lid_accuracy_pct": round(lid_acc, 1),
        }
        print(f"{lang.upper():12s} | {data['count']:7d} | {avg_wer:7.1f}% | {avg_cer:7.1f}% | {avg_rtf:8.3f} | {avg_lat:9.1f}ms | {lid_acc:6.1f}%")

    print("\n" + "=" * 80)
    print("  🌪️ PERFORMANCE BREAKDOWN BY ACOUSTIC STRESS CONDITION")
    print("=" * 80)
    print(f"{'Condition':25s} | {'Samples':7s} | {'Avg WER':8s} | {'Avg CER':8s} | {'Avg RTF':8s} | {'Avg Latency':11s}")
    print("-" * 80)

    cond_summary = {}
    for cond, data in sorted(results_by_condition.items()):
        avg_wer = np.mean(data["wers"]) * 100
        avg_cer = np.mean(data["cers"]) * 100
        avg_rtf = np.mean(data["rtfs"])
        avg_lat = np.mean(data["latencies"])
        cond_summary[cond] = {
            "samples": data["count"],
            "wer_pct": round(avg_wer, 1),
            "cer_pct": round(avg_cer, 1),
            "rtf": round(avg_rtf, 3),
            "latency_ms": round(avg_lat, 1),
        }
        print(f"{cond:25s} | {data['count']:7d} | {avg_wer:7.1f}% | {avg_cer:7.1f}% | {avg_rtf:8.3f} | {avg_lat:9.1f}ms")

    # Save JSON Report
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenarios_evaluated": len(detailed_records),
        "by_language": lang_summary,
        "by_condition": cond_summary,
        "detailed_records": detailed_records,
    }
    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Full JSON report written to: {REPORT_JSON_PATH}")

    # Generate Markdown Summary
    md_content = f"""# iTantra Multilingual Accuracy & Tactical Stress Report

**Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}  
**Total Evaluated Scenarios**: {len(detailed_records)}  
**Scope**: 10 Indian Languages + English across 6 Acoustic Stress Conditions

## 1. Performance by Language

| Language | Code | Evaluated Scenarios | Avg WER | Avg CER | Avg RTF | Avg Latency | LID Precision |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
"""
    for lang, s in sorted(lang_summary.items()):
        md_content += f"| **{lang.upper()}** | `{lang}` | {s['samples']} | **{s['wer_pct']}%** | **{s['cer_pct']}%** | {s['rtf']} | {s['latency_ms']} ms | {s['lid_accuracy_pct']}% |\n"

    md_content += """
## 2. Performance by Acoustic Stress Condition

| Acoustic Stress Scenario | Description | Avg WER | Avg CER | Avg RTF | Avg Latency |
|:---|:---|:---:|:---:|:---:|:---:|
"""
    for cond, s in sorted(cond_summary.items()):
        md_content += f"| **{cond}** | Harsh Battlefield Stress | **{s['wer_pct']}%** | **{s['cer_pct']}%** | {s['rtf']} | {s['latency_ms']} ms |\n"

    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"📄 Full Markdown report written to: {REPORT_MD_PATH}")
    return report_data


if __name__ == "__main__":
    run_benchmark()
