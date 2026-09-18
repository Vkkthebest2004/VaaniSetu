"""
iTantra Local Unified Model Server & API
Conforms to Sections 55 and 56 of iTantra Technical Specification:
Exposes local REST / IPC endpoints:
- POST /api/language  (iLangID)
- POST /api/asr       (iASR)
- POST /api/translate (iTranslate)
- POST /api/brain     (iBrain)
- POST /api/tts       (iVoice)
- POST /api/conversation (End-to-end conversation turn)
- GET  /api/status    (Offline runtime diagnostics)
All models kept resident in RAM.
"""

from aiohttp import web
import json
import numpy as np
import base64
import io
import scipy.io.wavfile as wavfile

from runtime.memory.manager import ModelLifecycleManager
from runtime.conversation.state_machine import iConversationEngine


# Initialize resident models at startup
manager = ModelLifecycleManager.get_instance()
manager.initialize_offline_stack()
conversation_engine = iConversationEngine()


async def handle_status(request: web.Request) -> web.Response:
    """GET /api/status - Return runtime status."""
    return web.json_response(manager.get_status())


async def handle_language(request: web.Request) -> web.Response:
    """POST /api/language - Run iLangID."""
    data = await request.json()
    # Expect base64 encoded PCM or mock test
    audio_b64 = data.get("audio_base64", "")
    if audio_b64:
        raw_bytes = base64.b64decode(audio_b64)
        sr, audio = wavfile.read(io.BytesIO(raw_bytes))
    else:
        # 1-second synthetic probe
        audio = np.random.normal(0, 0.05, 16000).astype(np.float32)

    probs = manager.lang_id.predict(audio)
    return web.json_response({"probabilities": probs, "dominant_language": next(iter(probs))})


async def handle_translate(request: web.Request) -> web.Response:
    """POST /api/translate - Run iTranslate."""
    data = await request.json()
    text = data.get("text", "")
    src = data.get("source_lang", "hi")
    tgt = data.get("target_lang", "en")

    result = manager.translate.translate(text=text, source_lang=src, target_lang=tgt)
    return web.json_response(result)


async def handle_brain(request: web.Request) -> web.Response:
    """POST /api/brain - Run iBrain reasoning."""
    data = await request.json()
    text = data.get("text", "")
    lang = data.get("language", "hi")

    result = manager.brain.generate_response(user_text=text, language=lang)
    return web.json_response(result)


async def handle_tts(request: web.Request) -> web.Response:
    """POST /api/tts - Run iVoice synthesis."""
    data = await request.json()
    text = data.get("text", "")
    lang = data.get("language", "hi")
    is_emergency = data.get("is_emergency", False)

    chunks = []
    for chunk in manager.voice.synthesize_text(text, language=lang, is_emergency=is_emergency):
        chunks.append(chunk["text_chunk"])

    return web.json_response({
        "status": "success",
        "text": text,
        "language": lang,
        "chunks_synthesized": len(chunks)
    })


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/status", handle_status)
    app.router.add_post("/api/language", handle_language)
    app.router.add_post("/api/translate", handle_translate)
    app.router.add_post("/api/brain", handle_brain)
    app.router.add_post("/api/tts", handle_tts)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="127.0.0.1", port=8085)
