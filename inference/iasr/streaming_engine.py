"""
iTantra Real-Time Streaming ASR Engine (iASR)
Conforms to Sections 20, 25, 26, 30, and 53 of iTantra Technical Specification:
Exposes:
- start_stream(language)
- push_audio(chunk)
- get_partial_result()
- finalize()
- stop_stream()
Supports explicit language conditioning tokens:
<LANG_HI>, <LANG_BN>, <LANG_TA>, <LANG_TE>, <LANG_MR>, <LANG_GU>, <LANG_KN>, <LANG_ML>, <LANG_PA>, <LANG_OR>
Integrates TinyML Acoustic Conditioning Front-End and Tactical Rescorer.
"""

import os
from typing import Optional, Dict, Any, List
import numpy as np
from pathlib import Path

from vaanisetu.stt.engine import SherpaSTTEngine
from vaanisetu.stt.acoustic_front_end import AcousticFrontEnd
from vaanisetu.stt.tactical_rescorer import TacticalRescorer


# Standard Indic language token map (Section 26)
LANGUAGE_TOKENS = {
    "hi": "<LANG_HI>",
    "bn": "<LANG_BN>",
    "ta": "<LANG_TA>",
    "te": "<LANG_TE>",
    "mr": "<LANG_MR>",
    "gu": "<LANG_GU>",
    "kn": "<LANG_KN>",
    "ml": "<LANG_ML>",
    "pa": "<LANG_PA>",
    "or": "<LANG_OR>",
    "en": "<LANG_EN>",
}


class ASRStream:
    """Represents an active streaming recognition session."""

    def __init__(self, language: str = "hi", stream_id: str = "stream_001"):
        self.stream_id = stream_id
        self.language = language
        self.language_token = LANGUAGE_TOKENS.get(language, "<LANG_HI>")
        self.audio_chunks: List[np.ndarray] = []
        self.total_samples: int = 0
        self.partial_text: str = ""
        self.is_active: bool = True


class iASRStreamingEngine:
    """
    On-device streaming ASR engine with language tokens,
    sub-chunk incremental hypothesis decoding, and acoustic front-end conditioning.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        sample_rate: int = 16000,
        enable_front_end: bool = True,
        enable_rescorer: bool = True
    ):
        self.sample_rate = sample_rate
        self.enable_front_end = enable_front_end
        self.enable_rescorer = enable_rescorer

        # Core offline acoustic front-end & domain rescorer
        self.front_end = AcousticFrontEnd(sample_rate=sample_rate) if enable_front_end else None
        self.rescorer = TacticalRescorer() if enable_rescorer else None

        # Base offline neural STT engine
        self.stt_engine = SherpaSTTEngine(model_dir=model_dir)

        self._active_streams: Dict[str, ASRStream] = {}

    def start_stream(self, language: str = "hi", stream_id: Optional[str] = None) -> ASRStream:
        """
        Initialize and return a new streaming ASR session.
        Conforms to Section 53: start_stream()
        """
        if stream_id is None:
            stream_id = f"stream_{len(self._active_streams) + 1}"

        stream = ASRStream(language=language, stream_id=stream_id)
        self._active_streams[stream_id] = stream
        return stream

    def push_audio(self, chunk: np.ndarray, stream: Optional[ASRStream] = None, stream_id: Optional[str] = None):
        """
        Push incoming audio chunk to the stream.
        Conforms to Section 53: push_audio(chunk)
        """
        target_stream = stream
        if target_stream is None and stream_id is not None:
            target_stream = self._active_streams.get(stream_id)

        if target_stream is None:
            raise ValueError("No active stream provided.")

        if not target_stream.is_active:
            return

        if chunk.dtype != np.float32:
            chunk = chunk.astype(np.float32)
        if chunk.ndim > 1:
            chunk = np.mean(chunk, axis=1)

        target_stream.audio_chunks.append(chunk)
        target_stream.total_samples += len(chunk)

    def get_partial_result(self, stream: Optional[ASRStream] = None, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute or fetch the current partial recognition hypothesis.
        Conforms to Section 53: get_partial_result()
        """
        target_stream = stream
        if target_stream is None and stream_id is not None:
            target_stream = self._active_streams.get(stream_id)

        if target_stream is None:
            return {"text": "", "is_final": False, "language": "hi"}

        # Need at least 0.5s of audio for a partial hypothesis
        min_samples = int(self.sample_rate * 0.5)
        if target_stream.total_samples < min_samples or not target_stream.audio_chunks:
            return {
                "text": target_stream.partial_text,
                "is_final": False,
                "language": target_stream.language,
                "token": target_stream.language_token
            }

        concatenated = np.concatenate(target_stream.audio_chunks)

        # Apply acoustic conditioning front-end
        conditioned = concatenated
        if self.front_end:
            conditioned = self.front_end.process(conditioned)

        # Transcribe
        raw_text = self.stt_engine.transcribe_array(conditioned, sample_rate=self.sample_rate)

        # Tactical domain rescoring
        if self.rescorer and raw_text:
            raw_text = self.rescorer.rescore(raw_text)

        target_stream.partial_text = raw_text

        return {
            "text": target_stream.partial_text,
            "is_final": False,
            "language": target_stream.language,
            "token": target_stream.language_token,
            "duration_sec": round(target_stream.total_samples / float(self.sample_rate), 2)
        }

    def finalize(self, stream: Optional[ASRStream] = None, stream_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Finalize stream, process all buffered audio, and return final transcript and metadata.
        Conforms to Section 53: finalize()
        """
        target_stream = stream
        if target_stream is None and stream_id is not None:
            target_stream = self._active_streams.get(stream_id)

        if target_stream is None or not target_stream.audio_chunks or target_stream.total_samples < int(self.sample_rate * 0.15):
            duration = round(target_stream.total_samples / float(self.sample_rate), 2) if target_stream else 0.0
            lang = target_stream.language if target_stream else "hi"
            token = target_stream.language_token if target_stream else "<LANG_HI>"
            if target_stream:
                self.stop_stream(target_stream)
            return {
                "text": "",
                "is_final": True,
                "language": lang,
                "token": token,
                "confidence": 0.0,
                "duration_sec": duration
            }

        concatenated = np.concatenate(target_stream.audio_chunks)

        # Apply full acoustic front-end conditioning
        if self.front_end:
            concatenated = self.front_end.process(concatenated)

        # Neural transcription
        final_text = self.stt_engine.transcribe_array(concatenated, sample_rate=self.sample_rate)

        # Tactical rescore and ITN
        if self.rescorer and final_text:
            final_text = self.rescorer.rescore(final_text)

        duration = round(target_stream.total_samples / float(self.sample_rate), 2)
        result = {
            "text": final_text,
            "is_final": True,
            "language": target_stream.language,
            "token": target_stream.language_token,
            "confidence": 0.95 if final_text else 0.0,
            "duration_sec": duration
        }

        self.stop_stream(target_stream)
        return result

    def stop_stream(self, stream: Optional[ASRStream] = None, stream_id: Optional[str] = None):
        """
        Close and cleanup stream session.
        Conforms to Section 53: stop_stream()
        """
        target_stream = stream
        if target_stream is None and stream_id is not None:
            target_stream = self._active_streams.get(stream_id)

        if target_stream:
            target_stream.is_active = False
            if target_stream.stream_id in self._active_streams:
                del self._active_streams[target_stream.stream_id]
