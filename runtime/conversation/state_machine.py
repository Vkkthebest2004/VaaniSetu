"""
iTantra Real-Time Conversation Engine & Barge-In State Machine (iConversation)
Conforms to Sections 48 and 49 of iTantra Technical Specification:
States:
- IDLE: Waiting for user speech
- LISTENING: User is speaking, capturing incoming audio frames
- PROCESSING: VAD detected speech end; running iLangID, iASR, Conversation Router, iTranslate/iBrain
- RESPONDING: iVoice TTS is generating and streaming audio to speaker
- INTERRUPTED: User spoke while iTantra was RESPONDING (Barge-In); TTS cut off immediately
- ERROR: Exception or hardware capture failure state
"""

from enum import Enum
import time
from typing import Optional, Dict, Any, Callable, List
import numpy as np

from audio.vad.silero_state_machine import iVADStateMachine, VADState
from inference.ilangid.classifier import iLangIDClassifier
from inference.iasr.streaming_engine import iASRStreamingEngine
from inference.ibrain.router import ConversationRouter, RouteDestination
from inference.ibrain.engine import iBrainEngine
from inference.itranslate.engine import iTranslateEngine
from inference.ivoice.streaming_tts import iVoiceStreamingEngine


class ConversationState(Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    RESPONDING = "RESPONDING"
    INTERRUPTED = "INTERRUPTED"
    ERROR = "ERROR"


class iConversationEngine:
    """
    Orchestrates the real-time conversation loop with seamless barge-in interruption.
    """

    def __init__(
        self,
        default_language: str = "hi",
        on_state_change: Optional[Callable[[ConversationState], None]] = None,
        on_audio_output: Optional[Callable[[np.ndarray], None]] = None
    ):
        self.current_state = ConversationState.IDLE
        self.current_language = default_language
        self.on_state_change = on_state_change
        self.on_audio_output = on_audio_output

        # Initialize subsystem engines
        self.vad = iVADStateMachine()
        self.lang_id = iLangIDClassifier()
        self.asr = iASRStreamingEngine()
        self.router = ConversationRouter()
        self.brain = iBrainEngine()
        self.translate = iTranslateEngine()
        self.voice = iVoiceStreamingEngine()

        # Audio buffers
        self.audio_buffer: List[np.ndarray] = []
        self.is_interrupted = False
        self.active_asr_stream = None

    def _set_state(self, new_state: ConversationState):
        """Transition conversation state."""
        self.current_state = new_state
        if self.on_state_change:
            self.on_state_change(new_state)

    def process_incoming_audio_chunk(self, chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process incoming microphone chunk in real-time.
        Handles VAD boundary detection and Barge-In triggers.
        """
        vad_res = self.vad.process_chunk(chunk)
        is_speech = vad_res["is_speech"]
        state_info = {"state": self.current_state, "action": None}

        # Check BARGE-IN: If system is currently RESPONDING and speech is detected
        if self.current_state == ConversationState.RESPONDING and is_speech:
            self.is_interrupted = True
            self._set_state(ConversationState.INTERRUPTED)
            # Stop TTS playback immediately
            self.audio_buffer.clear()
            self.audio_buffer.append(chunk)
            self.active_asr_stream = self.asr.start_stream(language=self.current_language)
            self.asr.push_audio(chunk, stream=self.active_asr_stream)
            self._set_state(ConversationState.LISTENING)
            state_info["action"] = "barge_in_triggered"
            return state_info

        # Normal State Machine Transitions
        if self.current_state == ConversationState.IDLE:
            if is_speech:
                self._set_state(ConversationState.LISTENING)
                self.audio_buffer = [chunk]
                self.active_asr_stream = self.asr.start_stream(language=self.current_language)
                self.asr.push_audio(chunk, stream=self.active_asr_stream)
                state_info["action"] = "speech_started"

        elif self.current_state == ConversationState.LISTENING:
            self.audio_buffer.append(chunk)
            if self.active_asr_stream:
                self.asr.push_audio(chunk, stream=self.active_asr_stream)

            if vad_res["utterance_completed"]:
                # User finished speaking!
                self._set_state(ConversationState.PROCESSING)
                full_audio = vad_res["utterance_audio"] if vad_res["utterance_audio"] is not None else np.concatenate(self.audio_buffer)
                response_data = self._process_utterance(full_audio)
                state_info["action"] = "utterance_processed"
                state_info["response"] = response_data

        return state_info

    def _process_utterance(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Execute the pipeline:
        Audio -> iLangID -> iASR -> Router -> (iTranslate / iBrain) -> iVoice -> RESPONDING
        """
        # 1. Automatic Language Identification
        detected_lang = self.lang_id.detect_dominant_language(audio)
        self.current_language = detected_lang

        # 2. ASR Finalization
        asr_res = self.asr.finalize(stream=self.active_asr_stream)
        user_text = asr_res["text"]
        self.active_asr_stream = None

        if not user_text.strip():
            self._set_state(ConversationState.IDLE)
            return {"text": "", "response_text": "", "language": detected_lang}

        # 3. Intent Routing
        decision, route_meta = self.router.route(user_text, detected_language=detected_lang)

        # 4. Processing via iTranslate or iBrain
        if decision == RouteDestination.SIMPLE_TRANSLATION:
            target_lang = route_meta.get("target_language", "en")
            trans_res = self.translate.translate(
                text=route_meta.get("clean_text_to_translate", user_text),
                source_lang=detected_lang,
                target_lang=target_lang
            )
            response_text = trans_res["translated_text"]
            resp_lang = target_lang
        else:
            brain_res = self.brain.generate_response(user_text, language=detected_lang)
            response_text = brain_res["response_text"]
            resp_lang = detected_lang

        # 5. Transition to RESPONDING & Stream TTS
        self._set_state(ConversationState.RESPONDING)
        self.is_interrupted = False

        tts_generator = self.voice.synthesize_text(response_text, language=resp_lang)
        synthesized_chunks = []

        for chunk_data in tts_generator:
            if self.is_interrupted:
                # Barge-in occurred! Halt speech immediately
                break
            audio_data = chunk_data["audio"]
            synthesized_chunks.append(audio_data)
            if self.on_audio_output:
                self.on_audio_output(audio_data)

        # Finished speaking, return to IDLE (or LISTENING if uninterrupted)
        if not self.is_interrupted:
            self._set_state(ConversationState.IDLE)

        return {
            "user_text": user_text,
            "detected_language": detected_lang,
            "decision": decision.value,
            "response_text": response_text,
            "response_language": resp_lang,
            "was_interrupted": self.is_interrupted
        }
