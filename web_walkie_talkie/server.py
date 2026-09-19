#!/usr/bin/env python3
"""
iTantra Walkie-Talkie Web Server & API
Provides live Push-to-Talk (PTT) walkie-talkie interface with dual-phone simulation,
real-time multilingual STT, ultra-low bitrate binary packet transceiver, and TTS voice playback.
Supports both Mac Hardware Microphone (direct SoundDevice) and Browser Web Audio.
"""

import os
import sys
import io
import time
import base64
import threading
import asyncio
import subprocess
import soundfile as sf
import sounddevice as sd
import numpy as np
from typing import Union, Optional, Dict
from pathlib import Path
from aiohttp import web

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vaanisetu.stt import MultilingualSTTEngine
from vaanisetu.tts import IndicTTSEngine
from vaanisetu.transceiver.protocol import (
    RadioPacket,
    PacketType,
    IndicLanguage,
    MicroRadioPacket,
    TacticalMacro,
    MACRO_PHRASES,
)
from vaanisetu.transceiver.wifi_mesh import WiFiMeshTransceiver

# Global engines
print("⏳ Initializing iTantra Neural Engines...")
_stt_engine = None
_indic_tts = None
_mesh = None

_transmission_id_counter = 0
_transmission_history = []


class HardwareRecorder:
    """Zero-overhead hardware microphone recorder on macOS CoreAudio."""

    def __init__(self):
        self.frames = []
        self.stream = None
        self.is_recording = False
        self.latest_peak = 0.0

    def start(self):
        self.frames = []
        self.is_recording = True
        self.latest_peak = 0.0

        def callback(indata, frame_count, time_info, status):
            if self.is_recording:
                self.frames.append(indata.copy())
                self.latest_peak = float(np.max(np.abs(indata)))

        try:
            dev_info = sd.query_devices(kind="input")
            dev_idx = dev_info["index"]
        except Exception:
            dev_idx = None

        try:
            self.stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=dev_idx,
                callback=callback,
            )
            self.stream.start()
            print(f"🎙️ Opened hardware mic stream on device {dev_idx}: {dev_info.get('name', 'Default Mic') if isinstance(dev_info, dict) else 'Default'}")
        except Exception as e:
            print(f"Error starting hardware mic stream: {e}")

    def stop(self) -> np.ndarray:
        self.is_recording = False
        self.latest_peak = 0.0
        stream = self.stream
        self.stream = None

        if stream:
            def _close_stream():
                try:
                    stream.stop()
                    stream.close()
                except Exception as e:
                    print(f"Stream close error: {e}")
            t = threading.Thread(target=_close_stream, daemon=True)
            t.start()

        if not self.frames:
            return np.array([], dtype=np.float32)
        return np.concatenate(self.frames).flatten()


_hw_recorder = HardwareRecorder()


def get_engines():
    global _stt_engine, _indic_tts, _mesh
    if _stt_engine is None:
        try:
            _stt_engine = MultilingualSTTEngine(num_threads=2)
        except Exception as e:
            print(f"Warning: Multilingual STT engine init: {e}")
    if _indic_tts is None:
        try:
            _indic_tts = IndicTTSEngine()
        except Exception as e:
            print(f"Warning: Indic TTS engine init: {e}")
    if _mesh is None:
        try:
            _mesh = WiFiMeshTransceiver(channel=7)
            _mesh.start(lambda pkt, addr: print(f"Mesh received packet from {addr}: {pkt.text}"))
        except Exception as e:
            print(f"Warning: Mesh init: {e}")
    return _stt_engine, _indic_tts, _mesh


def load_audio_any_format(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Decode audio bytes from any format (WAV, WebM, OGG, MP4, AAC)."""
    # 1. Try standard soundfile (for clean WAV)
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        return data, sr
    except Exception:
        pass

    # 2. Robust fallback: pipe through ffmpeg to raw 16kHz mono PCM
    try:
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-threads", "1",
            "-i", "pipe:0",
            "-f", "f32le",
            "-acodec", "pcm_f32le",
            "-ac", "1",
            "-ar", "16000",
            "pipe:1"
        ]
        proc = subprocess.run(cmd, input=audio_bytes, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
        pcm_data = np.frombuffer(proc.stdout, dtype=np.float32)
        if len(pcm_data) > 0:
            return pcm_data, 16000
    except Exception as e:
        print(f"FFmpeg decoding failed: {e}")

    return np.array([], dtype=np.float32), 16000


async def handle_index(request):
    """Serve the single-page Neural Walkie-Talkie interface."""
    html_path = PROJECT_ROOT / "web_walkie_talkie" / "index.html"
    return web.FileResponse(html_path)


async def handle_status(request):
    """Return system status and discovered mesh nodes."""
    stt_eng, tts_eng, mesh = get_engines()
    active_channel = 7
    nodes = ["Local Device (Mac CoreAudio)"]
    if mesh:
        active_channel = mesh.channel

    return web.json_response({
        "status": "online",
        "stt_ready": stt_eng is not None,
        "stt_model": "Whisper-Base Multilingual (INT8)",
        "tts_ready": tts_eng is not None,
        "tts_model": "VITS-Piper Indic (Hindi, Bengali, Tamil, etc.)",
        "active_channel": active_channel,
        "nodes_count": len(nodes),
        "nodes": nodes,
        "mic_recording": _hw_recorder.is_recording,
        "mic_peak": round(_hw_recorder.latest_peak, 4),
    })


async def handle_hw_ptt_start(request):
    """Start hardware microphone recording directly via macOS CoreAudio."""
    _hw_recorder.start()
    return web.json_response({"success": True, "recording": True})


LANGUAGE_NAMES = {
    "hi": "Hindi (हिंदी)",
    "bn": "Bengali (বাংলা)",
    "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)",
    "mr": "Marathi (मराठी)",
    "gu": "Gujarati (ગુજરાતી)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "ml": "Malayalam (മലയാളം)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "or": "Odia (ଓଡ଼ିଆ)",
    "en": "English",
}


def get_language_display_name(code: str) -> str:
    """Return user-friendly display name for 2-letter language code."""
    c = str(code).lower().strip()
    return LANGUAGE_NAMES.get(c, c.upper())


async def handle_hw_ptt_stop(request):
    """Stop hardware recording and process through Multilingual STT + Neural Transceiver."""
    stt_eng, tts_eng, mesh = get_engines()
    data = await request.json()

    lang_code = data.get("language", "hi")
    target_lang_code = data.get("target_language", "direct")
    channel = int(data.get("channel", 7))
    is_emergency = bool(data.get("is_emergency", False))
    language = IndicLanguage.from_code(lang_code)

    audio_data = _hw_recorder.stop()
    print(f"🎙️ Mac Hardware Mic: Stopped recording. Captured {len(audio_data)} samples ({len(audio_data)/16000:.2f}s).")

    if len(audio_data) < 2400:  # Less than 0.15s
        return web.json_response({
            "success": False,
            "error": "PTT was held for less than 0.2s. Please hold PTT while speaking."
        })

    peak = float(np.max(np.abs(audio_data)))
    rms = float(np.sqrt(np.mean(audio_data ** 2)))
    print(f"🎙️ Audio stats: peak={peak:.4f}, rms={rms:.4f}")

    if peak < 0.003:
        return web.json_response({
            "success": False,
            "error": "No voice detected. Please speak into your MacBook Pro microphone while holding PTT."
        })

    # Run Multilingual STT
    t0 = time.perf_counter()
    if stt_eng:
        text, detected_lang = stt_eng.transcribe_with_lang(
            audio_data, sample_rate=16000, language=lang_code, use_vad=True
        )
        if lang_code in ("", "auto", None):
            lang_code = detected_lang
            language = IndicLanguage.from_code(detected_lang)
    else:
        text = ""
    stt_latency_ms = (time.perf_counter() - t0) * 1000
    print(f"📝 Multilingual STT recognized text [{lang_code}]: '{text}' in {stt_latency_ms:.1f}ms")

    if not text:
        return web.json_response({
            "success": False,
            "error": "Speech was not recognized clearly. Please speak into your mic while holding PTT."
        })

    # Process packet & direct / cross-lingual TTS
    return execute_neural_transmission(
        text=text,
        source_language=lang_code,
        target_language=target_lang_code,
        channel=channel,
        is_emergency=is_emergency,
        audio_duration_sec=len(audio_data) / 16000,
        stt_latency_ms=stt_latency_ms
    )


async def handle_transmit(request):
    """Handle transmission with uploaded audio, manual text, or tactical macro."""
    stt_eng, tts_eng, mesh = get_engines()
    data = await request.json()

    text = data.get("text", "").strip()
    audio_b64 = data.get("audio", "")
    lang_code = data.get("language", "hi")
    target_lang_code = data.get("target_language", "direct")
    channel = int(data.get("channel", 7))
    is_emergency = bool(data.get("is_emergency", False))
    macro_id = int(data.get("macro", 0))

    language = IndicLanguage.from_code(lang_code)
    try:
        macro = TacticalMacro(macro_id) if macro_id > 0 else TacticalMacro.NONE
    except ValueError:
        macro = TacticalMacro.NONE

    if macro != TacticalMacro.NONE:
        is_emergency = True
        if not text:
            text = MACRO_PHRASES.get(macro, {}).get(language, "Emergency Alert")

    stt_latency_ms = 0.0
    audio_duration_sec = 2.5

    # 1. Process microphone audio if provided
    if audio_b64:
        try:
            audio_bytes = base64.b64decode(audio_b64)
            audio_data, sr = load_audio_any_format(audio_bytes)
            audio_duration_sec = len(audio_data) / sr
            peak = float(np.max(np.abs(audio_data))) if len(audio_data) > 0 else 0.0

            print(f"🎙️ Received browser audio: {len(audio_bytes)} bytes, {audio_duration_sec:.2f}s, sr={sr}, peak={peak:.4f}")

            if peak < 0.003 or len(audio_data) < int(sr * 0.15):
                return web.json_response({
                    "success": False,
                    "error": "Microphone audio was silent. Please switch to 'Mac Hardware Mic' mode above or check browser mic permission."
                })

            t0 = time.perf_counter()
            if stt_eng:
                text, detected_lang = stt_eng.transcribe_with_lang(
                    audio_data, sample_rate=sr, language=lang_code, use_vad=True
                )
                if lang_code in ("", "auto", None):
                    lang_code = detected_lang
                    language = IndicLanguage.from_code(detected_lang)
            stt_latency_ms = (time.perf_counter() - t0) * 1000
            print(f"📝 Multilingual STT recognized text [{lang_code}]: '{text}' in {stt_latency_ms:.1f}ms")

            if not text:
                return web.json_response({
                    "success": False,
                    "error": "Speech was not recognized clearly. Please speak closer to your microphone."
                })
        except Exception as e:
            print(f"Audio transcription error: {e}")
            return web.json_response({
                "success": False,
                "error": f"Audio processing error: {e}"
            })

    if not text:
        return web.json_response({
            "success": False,
            "error": "No message or speech was provided to transmit."
        })

    return execute_neural_transmission(
        text=text,
        source_language=lang_code,
        target_language=target_lang_code,
        channel=channel,
        is_emergency=is_emergency,
        audio_duration_sec=audio_duration_sec,
        stt_latency_ms=stt_latency_ms,
        macro=macro
    )


def execute_neural_transmission(
    text: str,
    source_language: Union[IndicLanguage, str],
    target_language: Union[IndicLanguage, str, None],
    channel: int,
    is_emergency: bool,
    audio_duration_sec: float,
    stt_latency_ms: float,
    macro: TacticalMacro = TacticalMacro.NONE,
):
    stt_eng, tts_eng, mesh = get_engines()

    # Normalize source language code
    if isinstance(source_language, IndicLanguage):
        src_code = source_language.to_code()
        language = source_language
    else:
        src_code = str(source_language or "hi").lower().strip()
        if src_code in ("auto", ""):
            src_code = "hi"
        language = IndicLanguage.from_code(src_code)

    # Normalize target language code
    if isinstance(target_language, IndicLanguage):
        tgt_code = target_language.to_code()
    elif target_language:
        tgt_code = str(target_language).lower().strip()
    else:
        tgt_code = "direct"

    # Direct Native Mode check:
    # If target is 'direct', 'native', or matches source, transmission is 100% direct native
    is_direct = (tgt_code in ("direct", "native", "same", "", None) or tgt_code == src_code)
    if is_direct:
        tgt_code = src_code

    # Construct ultra-compact MicroRadioPacket (Tier 1 Bit-packed header + Tier 2/3 compression)
    packet_type = (
        PacketType.TACTICAL_MACRO
        if macro != TacticalMacro.NONE
        else (PacketType.EMERGENCY_ALERT if is_emergency else PacketType.NORMAL_PTT)
    )

    micro_pkt = MicroRadioPacket(
        text=text,
        channel=channel,
        language=language,
        packet_type=packet_type,
        macro=macro,
        seq=int(time.time()) & 0x03,
    )
    serialized_bytes = micro_pkt.serialize()
    raw_pcm_bytes, packet_bytes, bandwidth_saving = micro_pkt.calculate_bandwidth_saving(audio_duration_sec)

    # Legacy RadioPacket for mesh broadcast compatibility
    legacy_pkt = RadioPacket(
        text=text,
        channel=channel,
        language=language,
        packet_type=packet_type,
    )

    if mesh:
        mesh.send_packet(legacy_pkt)

    simulated_airtime_ms = 1.2

    # 1. Determine Receiver Message Text:
    # In Direct Hindi-to-Hindi mode: NO conversion to English. Use exact natural Hindi speech!
    # In Cross-Lingual Translation mode: Translate offline to recipient's chosen Indian language.
    if is_direct:
        receiver_text = text
        translated_text = text
    else:
        try:
            from inference.itranslate.engine import iTranslateEngine
            _trans_eng = iTranslateEngine()
            trans_res = _trans_eng.translate(text, source_lang=src_code, target_lang=tgt_code)
            translated_text = trans_res.get("translated_text", text)
        except Exception as e:
            print(f"Offline translation error ({src_code} -> {tgt_code}): {e}")
            translated_text = text
        receiver_text = translated_text

    # 2. Receiver TTS synthesis:
    # Synthesize speech in target language (Hindi for direct mode, or target Indian language)
    t0 = time.perf_counter()
    synth_audio, synth_dur = tts_eng.synthesize(
        text=receiver_text,
        language=tgt_code,
        is_emergency=is_emergency,
        speed=1.0,
    )
    tts_latency_ms = (time.perf_counter() - t0) * 1000
    rtf = (tts_latency_ms / 1000.0) / synth_dur if synth_dur > 0 else 0.0

    # Encode receiver output audio to base64 WAV
    buf = io.BytesIO()
    sf.write(buf, synth_audio, tts_eng.sample_rate, format="WAV")
    output_audio_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    # If cross-lingual, also synthesize source audio so sender card can replay original voice
    source_audio_b64 = output_audio_b64
    if not is_direct and src_code != tgt_code:
        try:
            src_audio, _ = tts_eng.synthesize(
                text=text,
                language=src_code,
                is_emergency=is_emergency,
                speed=1.0,
            )
            s_buf = io.BytesIO()
            sf.write(s_buf, src_audio, tts_eng.sample_rate, format="WAV")
            source_audio_b64 = base64.b64encode(s_buf.getvalue()).decode("utf-8")
        except Exception:
            source_audio_b64 = output_audio_b64

    total_e2e_ms = stt_latency_ms + simulated_airtime_ms + tts_latency_ms

    global _transmission_id_counter, _transmission_history
    _transmission_id_counter += 1

    payload = {
        "id": _transmission_id_counter,
        "timestamp": time.strftime("%H:%M:%S"),
        "success": True,
        "source_text": text,
        "transcribed_text": text,
        "translated_text": translated_text,
        "receiver_text": receiver_text,
        "source_language": src_code,
        "source_language_name": get_language_display_name(src_code),
        "target_language": tgt_code,
        "target_language_name": get_language_display_name(tgt_code),
        "channel": channel,
        "language": src_code,
        "language_name": get_language_display_name(src_code),
        "is_emergency": is_emergency,
        "macro_id": int(macro),
        "macro_name": macro.name if macro != TacticalMacro.NONE else "",
        "audio_base64": output_audio_b64,
        "source_audio_base64": source_audio_b64,
        "sample_rate": tts_eng.sample_rate,
        "telemetry": {
            "packet_size_bytes": packet_bytes,
            "raw_voice_bytes": raw_pcm_bytes,
            "bandwidth_saving_pct": round(bandwidth_saving, 2),
            "stt_latency_ms": round(stt_latency_ms, 1),
            "airtime_latency_ms": round(simulated_airtime_ms, 1),
            "tts_latency_ms": round(tts_latency_ms, 1),
            "tts_rtf": round(rtf, 3),
            "total_e2e_latency_ms": round(total_e2e_ms, 1),
            "packet_hex": serialized_bytes.hex().upper(),
            "is_direct": is_direct,
            "mode": "DIRECT NATIVE" if is_direct else f"TRANSLATION ({src_code.upper()} -> {tgt_code.upper()})",
            "acoustic_front_end_active": True,
            "tactical_rescorer_active": True,
        }
    }

    _transmission_history.append(payload)
    if len(_transmission_history) > 100:
        _transmission_history.pop(0)

    return web.json_response(payload)


def generate_roger_beep(sample_rate: int = 16000) -> bytes:
    """Synthesize authentic dual-pip military tactical roger beep (1000Hz -> 1200Hz + squelch)."""
    pip1_dur = int(sample_rate * 0.035)  # 35ms
    pip2_dur = int(sample_rate * 0.035)  # 35ms
    squelch_dur = int(sample_rate * 0.025) # 25ms

    t1 = np.linspace(0, 0.035, pip1_dur, endpoint=False)
    t2 = np.linspace(0, 0.035, pip2_dur, endpoint=False)
    t3 = np.linspace(0, 0.025, squelch_dur, endpoint=False)

    tone1 = 0.45 * np.sin(2 * np.pi * 1000.0 * t1)
    # Hann window on tone 1
    tone1 *= np.hanning(pip1_dur)

    tone2 = 0.55 * np.sin(2 * np.pi * 1200.0 * t2)
    # Hann window on tone 2
    tone2 *= np.hanning(pip2_dur)

    # Squelch noise burst with exponential decay
    noise = np.random.uniform(-0.15, 0.15, squelch_dur) * np.exp(-t3 * 80)

    audio = np.concatenate([tone1, tone2, noise]).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV")
    return buf.getvalue()


def generate_siren_audio(duration_sec: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Synthesize dual-tone 960Hz / 770Hz warble emergency siren with +12dB gain."""
    total_samples = int(sample_rate * duration_sec)
    half_period = int(sample_rate * 0.25) # 250ms per tone
    audio = np.zeros(total_samples, dtype=np.float32)

    for i in range(total_samples):
        freq = 960.0 if (i // half_period) % 2 == 0 else 770.0
        audio[i] = np.sin(2 * np.pi * freq * (i / sample_rate))

    # Soft tanh saturation
    audio = np.tanh(audio * 3.5) * 0.95
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV")
    return buf.getvalue()


TACTICAL_MACRO_DEFINITIONS = [
    {
        "id": 1,
        "name": "MEDICAL_EVAC",
        "title": "Medical Evac",
        "icon": "🚑",
        "priority": "HIGH",
        "phrase_hi": "आपातकालीन चिकित्सा सहायता की तत्काल आवश्यकता है",
        "phrase_en": "Immediate medical evacuation required",
        "phrase_ta": "அவசர மருத்துவ உதவி தேவை",
        "phrase_bn": "জরুরী চিকিৎসা সহায়তা অবিলম্বে প্রয়োজন",
    },
    {
        "id": 2,
        "name": "FIRE_RESCUE",
        "title": "Fire Rescue",
        "icon": "🔥",
        "priority": "CRITICAL",
        "phrase_hi": "आग फैल रही है, अग्निशमन दल तुरंत भेजें",
        "phrase_en": "Fire spreading rapidly, dispatch fire rescue",
        "phrase_ta": "தீ பரவுகிறது, தீயணைப்பு படை தேவை",
        "phrase_bn": "আগুন দ্রুত ছড়াচ্ছে, ফায়ার রেসকিউ প্রয়োজন",
    },
    {
        "id": 3,
        "name": "FLOOD_EVAC",
        "title": "Flood Evac",
        "icon": "🌊",
        "priority": "HIGH",
        "phrase_hi": "जलस्तर बढ़ रहा है, नाव बचाव दल भेजें",
        "phrase_en": "Water level rising rapidly, dispatch boat rescue",
        "phrase_ta": "வெள்ளம் அதிகரிக்கிறது, படகுகள் தேவை",
        "phrase_bn": "পানির স্তর বাড়ছে, উদ্ধারকারী নৌকা পাঠান",
    },
    {
        "id": 4,
        "name": "HOSTAGE_AMBUSH",
        "title": "Hostage / Ambush",
        "icon": "🚨",
        "priority": "DISTRESS",
        "phrase_hi": "हम पर हमला हुआ है, तुरंत सुदृढ़ीकरण भेजें",
        "phrase_en": "Under ambush attack, send immediate reinforcements",
        "phrase_ta": "தாக்குதல் நடக்கிறது, உடனடி உதவி தேவை",
        "phrase_bn": "আক্রমণের মুখে, অবিলম্বে শক্তিবৃদ্ধি পাঠান",
    },
    {
        "id": 5,
        "name": "NEED_AMMO",
        "title": "Need Support",
        "icon": "⚡",
        "priority": "MEDIUM",
        "phrase_hi": "रसद और उपकरण की आवश्यकता है",
        "phrase_en": "Logistics and equipment resupply needed",
        "phrase_ta": "உபகரணங்கள் மற்றும் தளவாடங்கள் தேவை",
        "phrase_bn": "সরঞ্জাম এবং রসদ পুনরায় সরবরাহ প্রয়োজন",
    },
    {
        "id": 6,
        "name": "PERIMETER_BREACH",
        "title": "Perimeter Alert",
        "icon": "🛡️",
        "priority": "HIGH",
        "phrase_hi": "सुरक्षा घेरा टूट गया है, सतर्क रहें",
        "phrase_en": "Perimeter compromised, all units stay alert",
        "phrase_ta": "பாதுகாப்பு வட்டம் மீறப்பட்டது, எச்சரிக்கை",
        "phrase_bn": "সীমানা লঙ্ঘন হয়েছে, সতর্ক থাকুন",
    },
    {
        "id": 7,
        "name": "ALL_CLEAR",
        "title": "All Clear",
        "icon": "🟢",
        "priority": "NORMAL",
        "phrase_hi": "क्षेत्र सुरक्षित है, सब कुछ नियंत्रण में है",
        "phrase_en": "Sector all clear, situation under control",
        "phrase_ta": "பகுதி பாதுகாப்பானது, எல்லாம் கட்டுக்குள்",
        "phrase_bn": "এলাকা নিরাপদ, সবকিছু নিয়ন্ত্রণে",
    },
    {
        "id": 8,
        "name": "RENDEZVOUS",
        "title": "Rendezvous Point",
        "icon": "🧭",
        "priority": "NORMAL",
        "phrase_hi": "निर्धारित संपर्क बिंदु पर एकत्र हों",
        "phrase_en": "Regroup at designated rendezvous coordinates",
        "phrase_ta": "குறிப்பிட்ட இடத்தில் ஒன்று கூடுங்கள்",
        "phrase_bn": "নির্দিষ্ট মিলনস্থলে একত্রিত হন",
    },
]


async def handle_macros_list(request):
    """Return all tactical macro definitions."""
    return web.json_response({
        "success": True,
        "macros": TACTICAL_MACRO_DEFINITIONS
    })


async def handle_roger_beep_audio(request):
    """Return roger beep audio WAV."""
    audio_bytes = generate_roger_beep()
    return web.Response(body=audio_bytes, content_type="audio/wav")


async def handle_siren_audio(request):
    """Return emergency siren audio WAV."""
    audio_bytes = generate_siren_audio(duration_sec=2.0)
    return web.Response(body=audio_bytes, content_type="audio/wav")


async def handle_hw_mic_level(request):
    """Return live peak volume level from the hardware recorder."""
    return web.json_response({
        "is_recording": _hw_recorder.is_recording,
        "latest_peak": _hw_recorder.latest_peak,
    })


async def handle_sender(request):
    """Serve dedicated Field Transmitter Unit interface."""
    html_path = PROJECT_ROOT / "web_walkie_talkie" / "sender.html"
    return web.FileResponse(html_path)


async def handle_receiver(request):
    """Serve dedicated Command Listening Station interface."""
    html_path = PROJECT_ROOT / "web_walkie_talkie" / "receiver.html"
    return web.FileResponse(html_path)


async def handle_poll_ingress(request):
    """Poll for new transmissions since last_id for real-time receiver listening."""
    last_id = int(request.query.get("last_id", 0))
    ch_param = request.query.get("channel")
    channel_filter = int(ch_param) if ch_param and ch_param.isdigit() else None

    new_packets = [
        tx for tx in _transmission_history
        if tx["id"] > last_id and (channel_filter is None or tx["channel"] == channel_filter)
    ]
    return web.json_response({
        "success": True,
        "packets": new_packets,
        "latest_id": _transmission_id_counter
    })


async def handle_simulate_ingress(request):
    """Simulate a field voice or tactical macro transmission for receiver testing."""
    data = await request.json() if request.can_read_body else {}
    kind = data.get("type", "patrol")
    channel = int(data.get("channel", 8))
    lang_code = data.get("language", "hi")

    if kind == "medevac":
        macro = TacticalMacro.MEDICAL_URGENT
        text = "तत्काल चिकित्सा सहायता और एम्बुलेंस की आवश्यकता है"
        is_emergency = True
    elif kind == "fire":
        macro = TacticalMacro.FIRE_RESCUE
        text = "आग की आपात स्थिति • अग्निशमन दल तत्काल भेजें"
        is_emergency = True
    elif kind == "distress" or kind == "sos":
        macro = TacticalMacro.SEARCH_RESCUE
        text = "अत्यंत आपातकालीन स्थिति • तत्काल बैकअप और सहायता भेजें"
        is_emergency = True
    else:
        macro = TacticalMacro.NONE
        is_emergency = False
        sample_phrases = [
            "गश्त दल सुरक्षित है • सीमा चौकी पर सब ठीक है",
            "सेक्टर 4 में गश्त पूरी हो गई है, सभी जवान सुरक्षित हैं",
            "सप्लाई कॉन्वॉय बेस कैंप पर पहुंच गया है",
            "चेकपोस्ट अल्फा पर दृश्यता सामान्य है"
        ]
        text = data.get("text") or np.random.choice(sample_phrases)

    return execute_neural_transmission(
        text=text,
        source_language=lang_code,
        target_language="direct",
        channel=channel,
        is_emergency=is_emergency,
        audio_duration_sec=2.2,
        stt_latency_ms=65.0,
        macro=macro
    )


def create_app():
    get_engines()
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/sender", handle_sender)
    app.router.add_get("/receiver", handle_receiver)
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/poll_ingress", handle_poll_ingress)
    app.router.add_post("/api/simulate_ingress", handle_simulate_ingress)
    app.router.add_get("/api/hw_mic_level", handle_hw_mic_level)
    app.router.add_get("/api/macros", handle_macros_list)
    app.router.add_get("/api/roger_beep", handle_roger_beep_audio)
    app.router.add_get("/api/siren", handle_siren_audio)
    app.router.add_post("/api/transmit", handle_transmit)
    app.router.add_post("/api/hw_ptt_start", handle_hw_ptt_start)
    app.router.add_post("/api/hw_ptt_stop", handle_hw_ptt_stop)
    static_dir = Path(__file__).parent
    app.router.add_static("/static/", static_dir)
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"📻 Starting iTantra Walkie-Talkie on http://localhost:{port}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
