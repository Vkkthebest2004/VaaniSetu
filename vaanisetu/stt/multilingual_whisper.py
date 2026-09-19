"""
Multilingual STT Engine for iTantra Neural Transceiver.

Fully offline speech recognition supporting all 10 Indian languages:
1. Hindi (hi)
2. Bengali (bn)
3. Tamil (ta)
4. Telugu (te)
5. Marathi (mr)
6. Gujarati (gu)
7. Kannada (kn)
8. Malayalam (ml)
9. Punjabi (pa)
10. Odia (or)
Plus English (en) and automatic language detection.

Powered by int8 quantized Whisper models running on sherpa-onnx ONNX Runtime,
with acoustic front-end filtering, Silero VAD segmentation, and Indic script normalization.
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Union
import numpy as np
import sherpa_onnx

from .audio_utils import load_audio
from .vad import VoiceActivityDetector
from .acoustic_front_end import AcousticFrontEnd
from .tactical_rescorer import TacticalRescorer
from .indic_normalizer import IndicScriptNormalizer
from .config import STTConfig, default_stt_config
from ..transceiver.protocol import IndicLanguage

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class MultilingualSTTEngine:
    """
    State-of-the-Art Offline Multilingual Speech-to-Text Engine.
    
    Features:
    - Zero cloud dependency (100% on-device inference).
    - Multi-language support across 10 Indian languages + English.
    - Automatic spoken language identification (LID).
    - Sub-120ms latency per sentence via int8 quantized Whisper ONNX.
    - Acoustic noise gating and bandpass conditioning for harsh tactical environments.
    - Deterministic Indic script normalization (Urdu/Romanized -> native Devanagari/Indic).
    """

    SUPPORTED_LANGUAGES = {
        "hi": "Hindi",
        "bn": "Bengali",
        "ta": "Tamil",
        "te": "Telugu",
        "mr": "Marathi",
        "gu": "Gujarati",
        "kn": "Kannada",
        "ml": "Malayalam",
        "pa": "Punjabi",
        "or": "Odia",
        "en": "English",
        "ur": "Urdu",
    }

    # Language-specific prompt biasing to anchor Whisper to native script
    LANGUAGE_PROMPT_BIAS: Dict[str, str] = {
        "hi": "नमस्ते, यह आपातकालीन रेडियो संचार और आपदा राहत संदेश है।",
        "bn": "নমস্কার, এটি জরুরী রেডিও যোগাযোগ এবং উদ্ধার বার্তা।",
        "ta": "வணக்கம், இது அவசர வானொலி தொடர்பு மற்றும் மீட்பு செய்தி.",
        "te": "నమస్కారం, ఇది అత్యవసర రేడియో కమ్యూనికేషన్ మరియు రెస్క్యూ సందేశం.",
        "mr": "नमस्कार, हा आपत्कालीन रेडिओ संवाद आणि बचाव संदेश आहे.",
        "gu": "નમસ્તે, આ કટોકટી રેડિયો સંચાર અને બચાવ સંદેશ છે.",
        "kn": "ನಮಸ್ಕಾರ, ಇದು ತುರ್ತು ರೇಡಿಯೋ ಸಂವಹನ ಮತ್ತು ರಕ್ಷಣಾ ಸಂದೇಶ.",
        "ml": "നമസ്കാരം, ഇത് അടിയന്തര റേഡിയോ ആശയവിനിമയവും രക്ഷാ സന്ദേശവുമാണ്.",
        "pa": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਇਹ ਐਮਰਜੈਂਸੀ ਰੇਡੀਓ ਸੰਚਾਰ ਅਤੇ ਬਚਾਅ ਸੰਦੇਸ਼ ਹੈ।",
        "or": "ନମସ୍କାର, ଏହା ଜରୁରୀକାଳୀନ ରେଡିଓ ଯୋଗାଯୋଗ ଏବଂ ଉଦ୍ଧାର ବାର୍ତ୍ତା।",
        "en": "Emergency radio communications and tactical disaster alert.",
    }

    def __init__(
        self,
        model_name: str = "whisper-base",
        num_threads: int = 4,
        sample_rate: int = 16000,
    ):
        """
        Initialize the Multilingual STT Engine.

        Args:
            model_name: "whisper-base" (preferred, higher accuracy) or "whisper-tiny" (lightweight).
            num_threads: ONNX Runtime CPU inference threads.
            sample_rate: Target audio sample rate (default 16000 Hz).
        """
        self.sample_rate = sample_rate
        self.num_threads = num_threads
        self.model_name = model_name

        # Resolve model paths
        base_dir = _PROJECT_ROOT / "models" / "stt" / "sherpa-onnx-whisper-base"
        tiny_dir = _PROJECT_ROOT / "models" / "stt" / "sherpa-onnx-whisper-tiny"

        if model_name == "whisper-base" and base_dir.exists():
            self._model_dir = base_dir
            self._encoder = str(base_dir / "base-encoder.int8.onnx")
            self._decoder = str(base_dir / "base-decoder.int8.onnx")
            self._tokens = str(base_dir / "base-tokens.txt")
        elif tiny_dir.exists():
            self._model_dir = tiny_dir
            self._encoder = str(tiny_dir / "tiny-encoder.int8.onnx")
            self._decoder = str(tiny_dir / "tiny-decoder.int8.onnx")
            self._tokens = str(tiny_dir / "tiny-tokens.txt")
        else:
            raise FileNotFoundError(f"Whisper models not found in {_PROJECT_ROOT / 'models' / 'stt'}")

        # Thread-safe recognizer pool keyed by language code
        self._lock = threading.Lock()
        self._recognizers: Dict[str, sherpa_onnx.OfflineRecognizer] = {}

        # Acoustic Front-End and Tactical Conditioning
        self._front_end = AcousticFrontEnd(sample_rate=self.sample_rate)
        self._rescorer = TacticalRescorer()
        self._normalizer = IndicScriptNormalizer()

        # VAD for boundary detection
        vad_model_path = _PROJECT_ROOT / "models" / "vad" / "silero_vad.onnx"
        self._vad = None
        if vad_model_path.exists():
            vad_cfg = STTConfig(vad_model=str(vad_model_path))
            self._vad = VoiceActivityDetector(vad_cfg)

        # Pre-warm default languages (Hindi, English, auto)
        print(f"🚀 Initializing Multilingual STT ({self.model_name}) on {self.num_threads} threads...")
        self._get_recognizer("hi")
        self._get_recognizer("en")
        print(f"✅ Multilingual STT ready (supporting 10 Indian languages + English)")

    def _normalize_lang_code(self, language: Union[IndicLanguage, str, None]) -> str:
        """Converts language input into a standard 2-letter ISO code or empty string for auto."""
        if language is None:
            return ""
        if isinstance(language, IndicLanguage):
            return language.to_code()
        code = str(language).strip().lower()
        if code in ("auto", "none", "*", "detect"):
            return ""
        return code

    def _get_recognizer(self, lang_code: str) -> sherpa_onnx.OfflineRecognizer:
        """Retrieves or lazily instantiates a recognizer for the specified language."""
        with self._lock:
            if lang_code not in self._recognizers:
                t0 = time.perf_counter()
                rec = sherpa_onnx.OfflineRecognizer.from_whisper(
                    encoder=self._encoder,
                    decoder=self._decoder,
                    tokens=self._tokens,
                    language=lang_code,
                    task="transcribe",
                    num_threads=self.num_threads,
                    tail_paddings=0,
                )
                self._recognizers[lang_code] = rec
                dur = (time.perf_counter() - t0) * 1000
                lang_display = self.SUPPORTED_LANGUAGES.get(lang_code, lang_code or "Auto-Detect")
                print(f"   [STT] Loaded Whisper instance for {lang_display} [{lang_code or 'auto'}] in {dur:.1f}ms")
            return self._recognizers[lang_code]

    @staticmethod
    def trim_silence(
        audio: np.ndarray,
        sample_rate: int = 16000,
        threshold: float = 0.012,
        pad_sec: float = 0.15,
    ) -> np.ndarray:
        """
        Fast energy-based trimmer for leading and trailing silence/dead-air.
        Preserves pad_sec head/tail margin so initial and final phonemes are never clipped.
        """
        if len(audio) == 0:
            return audio
        frame_len = int(sample_rate * 0.02)  # 20ms frames
        n_frames = len(audio) // frame_len
        if n_frames < 3:
            return audio

        frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
        energy = np.sqrt(np.mean(frames ** 2, axis=1))
        speech_frames = np.where(energy > threshold)[0]

        if len(speech_frames) == 0:
            return audio

        pad_frames = int(pad_sec / 0.02)
        start_frame = max(0, speech_frames[0] - pad_frames)
        end_frame = min(n_frames, speech_frames[-1] + pad_frames + 1)

        return audio[start_frame * frame_len : end_frame * frame_len]

    def transcribe_array(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Union[IndicLanguage, str, None] = "hi",
        use_vad: bool = True,
    ) -> str:
        """
        Transcribes a NumPy audio array to clean text.

        Args:
            audio: 1D float32 audio waveform (-1.0 to 1.0).
            sample_rate: Audio sampling frequency.
            language: Target Indic language ('hi', 'bn', 'ta', etc. or IndicLanguage enum).
            use_vad: Whether to apply VAD noise gating / speech isolation.

        Returns:
            Clean, normalized transcript.
        """
        text, _ = self.transcribe_with_lang(
            audio=audio,
            sample_rate=sample_rate,
            language=language,
            use_vad=use_vad,
        )
        return text

    def transcribe_with_lang(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Union[IndicLanguage, str, None] = "hi",
        use_vad: bool = True,
    ) -> Tuple[str, str]:
        """
        Transcribes audio array and returns both text and detected language code.

        Returns:
            (transcript_text, detected_or_target_language_code)
        """
        if len(audio) == 0:
            return "", "en"

        # Resample to 16kHz if necessary
        if sample_rate != self.sample_rate:
            ratio = self.sample_rate / sample_rate
            num_samples = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio), num_samples, endpoint=False),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        # 1. Acoustic Front-End Conditioning (Whisper-safe AGC volume normalization)
        conditioned = self._front_end.process(audio, for_whisper=True)

        # 2. VAD Gating for Silence / Non-Speech (preserves full phonetic bursts)
        if use_vad and self._vad is not None:
            try:
                if not self._vad.has_speech(conditioned):
                    rms = np.sqrt(np.mean(conditioned ** 2))
                    if rms < 0.005:
                        return "", target_lang or "en"
            except Exception:
                pass

        if len(conditioned) < int(self.sample_rate * 0.15):  # Shorter than 150ms
            return "", target_lang or "en"

        # 3. Whisper ONNX Decoding
        target_lang = self._normalize_lang_code(language)
        # Whisper C++ decoder does not support 'or' as a standalone token code.
        # Fall back to 'bn' (Eastern Indo-Aryan sister language) for acoustic decoding
        whisper_lang = "bn" if target_lang == "or" else target_lang
        recognizer = self._get_recognizer(whisper_lang)

        # Fast trim leading/trailing dead air to minimize Whisper attention matrix length
        speech_audio = self.trim_silence(conditioned, sample_rate=self.sample_rate)
        if len(speech_audio) < int(self.sample_rate * 0.15):
            speech_audio = conditioned

        stream = recognizer.create_stream()
        prompt = self.LANGUAGE_PROMPT_BIAS.get(target_lang or whisper_lang)
        if prompt:
            try:
                stream.set_option("prompt", prompt)
            except Exception:
                pass
        stream.accept_waveform(self.sample_rate, speech_audio)
        recognizer.decode_stream(stream)

        raw_text = stream.result.text.strip()
        detected_lang = stream.result.lang or target_lang or "hi"

        if not raw_text:
            return "", target_lang or detected_lang

        # 4. Indic Script Normalization & Rescoring
        clean_text = self._normalizer.normalize(raw_text, target_lang=target_lang or detected_lang)
        final_text = self._rescorer.rescore(clean_text, language=target_lang or detected_lang)

        return final_text, (target_lang or detected_lang)

    def transcribe(
        self,
        audio_input: Union[str, np.ndarray],
        sample_rate: int = 16000,
        language: Union[IndicLanguage, str, None] = "hi",
        use_vad: bool = True,
    ) -> str:
        """
        Universal transcribe entry point for either audio file paths or numpy arrays.
        """
        if isinstance(audio_input, (str, Path)):
            audio, sr = load_audio(str(audio_input), target_sr=self.sample_rate)
            return self.transcribe_array(audio, sample_rate=sr, language=language, use_vad=use_vad)
        elif isinstance(audio_input, np.ndarray):
            return self.transcribe_array(audio_input, sample_rate=sample_rate, language=language, use_vad=use_vad)
        else:
            raise ValueError(f"Unsupported audio input type: {type(audio_input)}")

    def process_ptt_audio(
        self,
        audio_chunks: List[np.ndarray],
        sample_rate: int = 16000,
        language: Union[IndicLanguage, str, None] = "hi",
    ) -> str:
        """
        Processes concatenated audio chunks from a Push-to-Talk (PTT) session.
        """
        if not audio_chunks:
            return ""

        full_audio = np.concatenate(audio_chunks).astype(np.float32)
        rms = np.sqrt(np.mean(full_audio ** 2))
        if rms < 0.003:
            return ""

        return self.transcribe_array(
            audio=full_audio,
            sample_rate=sample_rate,
            language=language,
            use_vad=True,
        )
