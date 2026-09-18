"""
Comprehensive integration tests for iTantra AI Stack:
iVAD, iLangID, iASR Streaming, iTranslate, ConversationRouter, iBrain, iVoice, and Barge-In.
"""

import numpy as np
import pytest

from audio.vad.silero_state_machine import iVADStateMachine, VADState
from inference.ilangid.classifier import iLangIDClassifier
from inference.iasr.streaming_engine import iASRStreamingEngine
from inference.itranslate.engine import iTranslateEngine
from inference.ibrain.router import ConversationRouter, RouteDestination
from inference.ibrain.engine import iBrainEngine
from inference.ivoice.streaming_tts import iVoiceStreamingEngine
from runtime.conversation.state_machine import iConversationEngine, ConversationState
from evaluation.asr.evaluator import ASREvaluator


def test_ivad_state_machine_transitions():
    import scipy.io.wavfile as wavfile
    from pathlib import Path
    vad = iVADStateMachine(threshold=0.35, min_speech_duration_ms=50.0, min_silence_duration_ms=100.0)
    assert vad.state == VADState.IDLE

    # Push actual speech chunks from tts_output.wav
    candidates = [Path("audio/samples/tts_output.wav"), Path("tts_output.wav")]
    wav_path = next((p for p in candidates if p.exists()), candidates[0])
    if wav_path.exists():
        sr, audio = wavfile.read(str(wav_path))
        audio = audio.astype(np.float32) / 32768.0
        # Push first few speech chunks
        for i in range(1000, 6000, 512):
            chunk = audio[i:i + 512]
            if len(chunk) == 512:
                res = vad.process_chunk(chunk)
    else:
        # Energy fallback simulation
        vad._using_sherpa = False
        speech_chunk = np.ones(512, dtype=np.float32) * 0.1
        for _ in range(5):
            res = vad.process_chunk(speech_chunk)

    assert vad.state in [VADState.SPEAKING, VADState.POSSIBLE_END]


def test_ilangid_classifier_returns_all_10_languages():
    classifier = iLangIDClassifier()
    audio = np.random.normal(0, 0.1, 16000).astype(np.float32)

    probs = classifier.predict(audio, sample_rate=16000)
    for lang in ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or"]:
        assert lang in probs
        assert 0.0 <= probs[lang] <= 1.0

    assert abs(sum(probs.values()) - 1.0) < 0.05
    dominant = classifier.detect_dominant_language(audio)
    assert dominant in classifier.SUPPORTED_LANGUAGES


def test_iasr_streaming_lifecycle():
    engine = iASRStreamingEngine()
    stream = engine.start_stream(language="hi", stream_id="test_stream")

    assert stream.is_active is True
    assert stream.language_token == "<LANG_HI>"

    # Push audio chunks (0.5s of audio)
    audio_chunk = np.random.normal(0, 0.05, 8000).astype(np.float32)
    engine.push_audio(audio_chunk, stream=stream)
    assert stream.total_samples == 8000

    partial = engine.get_partial_result(stream=stream)
    assert "text" in partial
    assert partial["token"] == "<LANG_HI>"

    final_res = engine.finalize(stream=stream)
    assert "text" in final_res
    assert final_res["is_final"] is True


def test_itranslate_and_router():
    router = ConversationRouter()
    translate_engine = iTranslateEngine()

    # Route: Simple translation
    dest_trans, meta_trans = router.route("translate this into Tamil: medical urgent")
    assert dest_trans == RouteDestination.SIMPLE_TRANSLATION
    assert meta_trans["target_language"] == "ta"

    # Execute translation
    res_trans = translate_engine.translate(text="medical urgent", source_lang="en", target_lang="ta")
    assert "அவசர மருத்துவ உதவி தேவை" in res_trans["translated_text"]

    # Route: Contextual reasoning
    dest_reason, _ = router.route("What should I do if flood water is rising?")
    assert dest_reason == RouteDestination.REASONING_REQUIRED


def test_ibrain_concise_response():
    brain = iBrainEngine()
    resp = brain.generate_response(user_text="बाढ़ का पानी आ गया है", language="hi")

    assert "response_text" in resp
    assert len(resp["response_text"]) > 0
    # Voice-friendly brevity check: <= 2 sentences
    assert resp["response_text"].count("।") <= 2


def test_ivoice_streaming_clause_splitting():
    voice = iVoiceStreamingEngine()
    text = "नमस्ते। आई-तंत्रा सक्रिय है। कृपया अपना संदेश बोलें।"
    chunks = voice.split_into_chunks(text)

    assert len(chunks) >= 2
    assert "नमस्ते" in chunks[0]


def test_iconversation_barge_in():
    convo = iConversationEngine()
    assert convo.current_state == ConversationState.IDLE

    # Simulate system currently speaking to user (RESPONDING)
    convo._set_state(ConversationState.RESPONDING)

    # User starts speaking (Barge-In)
    from pathlib import Path
    import scipy.io.wavfile as wavfile
    candidates = [Path("audio/samples/tts_output.wav"), Path("tts_output.wav")]
    wav_path = next((p for p in candidates if p.exists()), candidates[0])
    triggered = False

    if wav_path.exists():
        _, audio = wavfile.read(str(wav_path))
        audio = audio.astype(np.float32) / 32768.0
        for i in range(0, len(audio) - 512, 512):
            chunk = audio[i:i + 512]
            res = convo.process_incoming_audio_chunk(chunk)
            if res.get("action") == "barge_in_triggered":
                triggered = True
                break
    else:
        convo.vad._using_sherpa = False
        speech_chunk = np.ones(512, dtype=np.float32) * 0.1
        res = convo.process_incoming_audio_chunk(speech_chunk)
        triggered = (res.get("action") == "barge_in_triggered")

    # Must transition out of RESPONDING to handle user interruption
    assert triggered is True
    assert convo.current_state == ConversationState.LISTENING


def test_asr_evaluator_metrics():
    evaluator = ASREvaluator()

    ref = "मुझे दिल्ली जाना है"
    hyp_exact = "मुझे दिल्ली जाना है"
    assert evaluator.calculate_wer(ref, hyp_exact) == 0.0
    assert evaluator.calculate_cer(ref, hyp_exact) == 0.0

    hyp_sub = "मुझे मुंबई जाना है"
    assert evaluator.calculate_wer(ref, hyp_sub) == 0.25  # 1 substitution out of 4 words

    rtf = evaluator.calculate_rtf(processing_time_sec=0.2, audio_duration_sec=2.0)
    assert rtf == 0.1  # 10x faster than real-time
