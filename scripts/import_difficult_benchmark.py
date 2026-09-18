#!/usr/bin/env python3
"""
Difficult Multilingual Benchmark Audio Importer & Stress Synthesizer
for iTantra / VaaniSetu Neural Transceiver.

Generates a standardized, highly challenging benchmark suite across:
- All 10 Indian Languages (hi, bn, ta, te, mr, gu, kn, ml, pa, or) + English (en).
- 3 Emergency / Tactical Domains (Evacuation, Medical/Rescue, Radio Check-in).
- 5 Extreme Acoustic Stress Conditions:
  1. Clean Native Baseline
  2. Cockpit Rotorcraft & Turbine Noise (0 dB SNR)
  3. Emergency G.711 Telephone Channel (300-3400Hz + 8-bit companding + line hiss)
  4. Artillery Overpressure Shockwave Transient
  5. Low-Amplitude Post-Blast Survivor Whisper (RMS < 0.01)
  6. Urgent Panic Cadence (1.25x tempo)

Generates standardized 16kHz Mono WAVs in datasets/evaluation/ and manifests/evaluation_manifest.csv.
"""

import os
import sys
import csv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import soundfile as sf
from typing import Dict, List, Tuple

from vaanisetu.tts.indic_tts import IndicTTSEngine
from audio.preprocessing.telephone import TelephoneSimulator
from benchmarks.military_stress_test import BattlefieldAcousticSimulator
from vaanisetu.stt.audio_utils import load_audio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "datasets" / "evaluation"
MANIFEST_PATH = EVAL_DIR / "manifest.csv"

# Comprehensive Tactical & Emergency Corpus across 10 Indian Languages + English
BENCHMARK_CORPUS: Dict[str, List[Tuple[str, str]]] = {
    "hi": [
        ("evacuation", "बाढ़ का पानी बढ़ रहा है तुरंत खाली करें"),
        ("medical", "चिकित्सा आपातकाल तत्काल सहायता चाहिए"),
        ("checkin", "नमस्ते आप कैसे हैं यह वाणी सेतु है"),
    ],
    "bn": [
        ("evacuation", "বন্যার জল বাড়ছে অবিলম্বে খালি করুন"),
        ("medical", "জরুরী চিকিৎসা প্রয়োজন অবিলম্বে দল পাঠান"),
        ("checkin", "নমস্কার আপনি কেমন আছেন এটি বাণী সেতু"),
    ],
    "ta": [
        ("evacuation", "வெள்ள நீர் உயர்கிறது உடனடியாக வெளியேறுங்கள்"),
        ("medical", "அவசர மருத்துவ உதவி தேவை உடனடியாக வாருங்கள்"),
        ("checkin", "வணக்கம் நீங்கள் எப்படி இருக்கிறீர்கள் இது வாணி சேது"),
    ],
    "te": [
        ("evacuation", "వరద నీరు పెరుగుతోంది వెంటనే ఖాళీ చేయండి"),
        ("medical", "తక్షణ వైద్య సహాయం అవసరం వెంటనే రండి"),
        ("checkin", "నమస్కారం మీరు ఎలా ఉన్నారు ఇది వాణి సేతు"),
    ],
    "mr": [
        ("evacuation", "पुराचे पाणी वाढत आहे त्वरित रिकामे करा"),
        ("medical", "तातडीची वैद्यकीय मदत हवी आहे त्वरित या"),
        ("checkin", "नमस्कार तुम्ही कसे आहात हे वाणी सेतू आहे"),
    ],
    "gu": [
        ("evacuation", "પૂરનું પાણી વધી રહ્યું છે તરત જ ખાલી કરો"),
        ("medical", "તાત્કાલિક તબીબી સહાયની જરૂર છે ટીમ મોકલો"),
        ("checkin", "નમસ્તે તમે કેમ છો આ વાણી સેતુ છે"),
    ],
    "kn": [
        ("evacuation", "ಪ್ರವಾಹದ ನೀರು ಏರುತ್ತಿದೆ ತಕ್ಷಣವೇ ಖಾಲಿ ಮಾಡಿ"),
        ("medical", "ತುರ್ತು ವೈದ್ಯಕೀಯ ನೆರವು ಬೇಕು ತಂಡವನ್ನು ಕಳುಹಿಸಿ"),
        ("checkin", "ನಮಸ್ಕಾರ ನೀವು ಹೇಗಿದ್ದೀರಿ ಇದು ವಾಣಿ ಸೇತು"),
    ],
    "ml": [
        ("evacuation", "വെള്ളപ്പൊക്ക ജലം ഉയരുന്നു ഉടൻ മാറുക"),
        ("medical", "അടിയന്തിര വൈദ്യസഹായം വേണം സംഘത്തെ അയക്കുക"),
        ("checkin", "നമസ്കാരം സുഖമാണോ ഇത് വാണി സേതുവാണ്"),
    ],
    "pa": [
        ("evacuation", "ਹੜ੍ਹ ਦਾ ਪਾਣੀ ਵੱਧ ਰਿਹਾ ਹੈ ਤੁਰੰਤ ਖਾਲੀ ਕਰੋ"),
        ("medical", "ਤੁਰੰਤ ਡਾਕਟਰੀ ਸਹਾਇਤਾ ਚਾਹੀਦੀ ਹੈ ਟੀਮ ਭੇਜੋ"),
        ("checkin", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ ਇਹ ਵਾਣੀ ਸੇਤੂ ਹੈ"),
    ],
    "or": [
        ("evacuation", "ବନ୍ୟା ଜଳ ବୃଦ୍ଧି ପାଉଛି ତୁରନ୍ତ ଖାଲି କରନ୍ତୁ"),
        ("medical", "ତୁରନ୍ତ ଡାକ୍ତରୀ ସାହାଯ୍ୟ ଆବଶ୍ୟକ ଟିମ ପଠାନ୍ତୁ"),
        ("checkin", "ନମସ୍କାର ଆପଣ କେମିତି ଅଛନ୍ତି ଏହା ବାଣୀ ସେତୁ"),
    ],
    "en": [
        ("evacuation", "Flood water rising evacuate immediately"),
        ("medical", "Urgent medical assistance needed send rescue team"),
        ("checkin", "Hello how are you this is VaaniSetu radio"),
    ],
}


def create_difficult_benchmark():
    """Generates the full suite of challenging audio test cases."""
    print("🚀 Initializing Difficult Multilingual Audio Generator...")
    tts = IndicTTSEngine()
    tel_sim = TelephoneSimulator(sample_rate=16000)
    battle_sim = BattlefieldAcousticSimulator(sample_rate=16000)

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    manifest_rows = []

    # Check if we have real Hindi test audio
    real_hindi_candidates = [
        PROJECT_ROOT / "audio" / "samples" / "hindi_test.wav",
        PROJECT_ROOT / "hindi_test.wav"
    ]
    real_hindi_path = next((p for p in real_hindi_candidates if p.exists()), real_hindi_candidates[0])
    real_hindi_audio = None
    if real_hindi_path.exists():
        real_hindi_audio, _ = load_audio(str(real_hindi_path), target_sr=16000)
        print(f"🎙️ Found real human Hindi recording ({len(real_hindi_audio)/16000:.1f}s)")

    for lang, phrases in BENCHMARK_CORPUS.items():
        lang_dir = EVAL_DIR / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n📦 Processing Language: {lang.upper()} ({len(phrases)} base phrases)...")

        for idx, (category, phrase_text) in enumerate(phrases):
            # 1. Generate clean base 16kHz audio
            if lang == "hi" and category == "checkin" and real_hindi_audio is not None:
                base_audio = real_hindi_audio.copy()
            else:
                raw_synth, _ = tts.synthesize(phrase_text, language=lang, speed=1.0)
                # Resample from 22050 to 16000 if necessary
                if tts.sample_rate != 16000:
                    num_samples = int(len(raw_synth) * 16000 / tts.sample_rate)
                    base_audio = np.interp(
                        np.linspace(0, len(raw_synth), num_samples, endpoint=False),
                        np.arange(len(raw_synth)),
                        raw_synth,
                    ).astype(np.float32)
                else:
                    base_audio = raw_synth.astype(np.float32)

            # Peak normalize base audio
            peak = np.max(np.abs(base_audio))
            if peak > 0:
                base_audio = (base_audio / peak) * 0.85

            duration_sec = len(base_audio) / 16000.0

            # -------------------------------------------------------------
            # Condition 1: Clean Native Baseline
            # -------------------------------------------------------------
            c1_path = lang_dir / f"{idx}_clean_{category}.wav"
            sf.write(str(c1_path), base_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c1_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "clean",
                "reference_text": phrase_text,
                "duration_sec": round(duration_sec, 2),
            })

            # -------------------------------------------------------------
            # Condition 2: Cockpit Rotorcraft & Turbine Noise (0 dB SNR)
            # -------------------------------------------------------------
            drone_noise = battle_sim.generate_rotorcraft_drone(duration_sec=duration_sec)
            c2_audio = battle_sim.mix_at_snr(base_audio, drone_noise, snr_db=0.0)
            c2_path = lang_dir / f"{idx}_drone_0db_{category}.wav"
            sf.write(str(c2_path), c2_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c2_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "drone_0db",
                "reference_text": phrase_text,
                "duration_sec": round(duration_sec, 2),
            })

            # -------------------------------------------------------------
            # Condition 3: Emergency Telephone Channel (G.711 + Bandpass)
            # -------------------------------------------------------------
            c3_audio = tel_sim.apply_telephone_filter(base_audio)
            c3_audio = tel_sim.simulate_g711_mulaw(c3_audio)
            c3_audio = tel_sim.add_line_noise(c3_audio, snr_db=15.0)
            c3_path = lang_dir / f"{idx}_telephone_g711_{category}.wav"
            sf.write(str(c3_path), c3_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c3_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "telephone_g711",
                "reference_text": phrase_text,
                "duration_sec": round(duration_sec, 2),
            })

            # -------------------------------------------------------------
            # Condition 4: Artillery Transient Shockwave
            # -------------------------------------------------------------
            c4_audio = base_audio.copy()
            blast = battle_sim.generate_artillery_blast_transient(duration_sec=0.3)
            # Inject blast at mid-point of sentence
            mid = len(c4_audio) // 2
            blast_len = min(len(blast), len(c4_audio) - mid)
            c4_audio[mid:mid + blast_len] += blast[:blast_len]
            # Soft clip limiter
            c4_audio = np.clip(c4_audio, -0.95, 0.95)
            c4_path = lang_dir / f"{idx}_artillery_blast_{category}.wav"
            sf.write(str(c4_path), c4_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c4_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "artillery_blast",
                "reference_text": phrase_text,
                "duration_sec": round(duration_sec, 2),
            })

            # -------------------------------------------------------------
            # Condition 5: Low-Amplitude Trapped Survivor Whisper
            # -------------------------------------------------------------
            c5_audio = base_audio * 0.05  # Scale down to RMS ~0.005
            # Add faint room ambience
            ambient_noise = np.random.normal(0, 0.001, len(c5_audio)).astype(np.float32)
            c5_audio = (c5_audio + ambient_noise).astype(np.float32)
            c5_path = lang_dir / f"{idx}_whisper_low_{category}.wav"
            sf.write(str(c5_path), c5_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c5_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "whisper_low",
                "reference_text": phrase_text,
                "duration_sec": round(duration_sec, 2),
            })

            # -------------------------------------------------------------
            # Condition 6: Urgent Panic Cadence (1.25x Fast Speech)
            # -------------------------------------------------------------
            raw_fast, _ = tts.synthesize(phrase_text, language=lang, speed=1.25)
            if tts.sample_rate != 16000:
                fast_samples = int(len(raw_fast) * 16000 / tts.sample_rate)
                c6_audio = np.interp(
                    np.linspace(0, len(raw_fast), fast_samples, endpoint=False),
                    np.arange(len(raw_fast)),
                    raw_fast,
                ).astype(np.float32)
            else:
                c6_audio = raw_fast.astype(np.float32)
            c6_path = lang_dir / f"{idx}_urgent_fast_{category}.wav"
            sf.write(str(c6_path), c6_audio, 16000, subtype="PCM_16")
            manifest_rows.append({
                "audio_path": str(c6_path.relative_to(PROJECT_ROOT)),
                "language": lang,
                "category": category,
                "condition": "urgent_fast",
                "reference_text": phrase_text,
                "duration_sec": round(len(c6_audio) / 16000.0, 2),
            })

    # Write manifest CSV
    with open(MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "audio_path", "language", "category", "condition", "reference_text", "duration_sec"
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\n✅ Successfully generated {len(manifest_rows)} difficult test audio files!")
    print(f"📄 Manifest written to: {MANIFEST_PATH}")


if __name__ == "__main__":
    create_difficult_benchmark()
