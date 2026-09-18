"""
iTantra Streaming Text-to-Speech Engine (iVoice)
Conforms to Sections 44, 46, 47, and 54 of iTantra Technical Specification:
Features:
- Multilingual speech synthesis across 10 Indian languages (+ English)
- Clause-by-clause and sentence chunk streaming:
  text_chunk -> TTS -> audio_chunk -> play immediately
- Pre-annunciation emergency alert siren generator (+12dB)
- Sub-50ms first-audio generation latency
"""

import re
from typing import Iterator, Dict, Any, Optional, List
import numpy as np
from pathlib import Path

from vaanisetu.tts.indic_tts import IndicTTSEngine


class iVoiceStreamingEngine:
    """
    Streaming TTS Engine capable of receiving streamed text tokens
    and emitting synthesized audio chunks incrementally.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        sample_rate: int = 22050,
        enable_emergency_siren: bool = True
    ):
        self.sample_rate = sample_rate
        self.enable_emergency_siren = enable_emergency_siren

        # Offline Indic TTS engine (Piper VITS / multi-accent synthesizers)
        from vaanisetu.tts.engine import SherpaTTSEngine
        base_tts = SherpaTTSEngine(model_dir=model_path) if model_path else None
        self.tts_engine = IndicTTSEngine(tts_engine=base_tts)

    def split_into_chunks(self, text: str) -> List[str]:
        """
        Split text stream into natural speech clauses by punctuation.
        Enables synthesis of clause 1 while clause 2 is still being generated.
        """
        if not text:
            return []

        # Split on sentence boundaries, dandas, commas, semicolons
        chunks = re.split(r'([।॥\.\?!,;:\n]+)', text)
        merged = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i].strip()
            if i + 1 < len(chunks):
                # Attach the punctuation
                punct = chunks[i + 1].strip()
                if chunk:
                    merged.append(f"{chunk} {punct}".strip())
                i += 2
            else:
                if chunk:
                    merged.append(chunk)
                i += 1

        return merged if merged else [text.strip()]

    def synthesize_stream(
        self,
        text_stream: Iterator[str],
        language: str = "hi",
        is_emergency: bool = False
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream synthesized audio chunks as text chunks arrive.
        Conforms to Section 54:
        for text_chunk in response_stream:
            audio_chunk = tts.generate(text_chunk)
            audio_player.play(audio_chunk)

        Yields:
            {
                "audio": np.ndarray (float32, 22050Hz mono),
                "text_chunk": str,
                "is_first_chunk": bool,
                "is_last_chunk": bool
            }
        """
        is_first = True

        # Prepend emergency siren chime if emergency
        if is_emergency and self.enable_emergency_siren:
            siren_audio = self.tts_engine.generate_emergency_siren(duration_sec=0.4)
            yield {
                "audio": siren_audio,
                "text_chunk": "[EMERGENCY SIREN]",
                "is_first_chunk": True,
                "is_last_chunk": False
            }
            is_first = False

        for chunk_text in text_stream:
            if not chunk_text or not chunk_text.strip():
                continue

            audio = self.tts_engine.synthesize(
                text=chunk_text.strip(),
                language=language,
                is_emergency=is_emergency
            )

            yield {
                "audio": audio,
                "text_chunk": chunk_text,
                "is_first_chunk": is_first,
                "is_last_chunk": False
            }
            is_first = False

    def synthesize_text(
        self,
        full_text: str,
        language: str = "hi",
        is_emergency: bool = False
    ) -> Iterator[Dict[str, Any]]:
        """Synthesize a complete string by breaking it into streaming clauses."""
        chunks = self.split_into_chunks(full_text)
        return self.synthesize_stream(iter(chunks), language=language, is_emergency=is_emergency)
