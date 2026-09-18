"""
Unit tests for iTantra Runtime Lifecycle Manager and Local API Server.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from runtime.memory.manager import ModelLifecycleManager
from runtime.server import create_app


def test_model_lifecycle_manager():
    manager = ModelLifecycleManager.get_instance()
    status = manager.initialize_offline_stack()

    assert status["is_initialized"] is True
    assert status["offline_ready"] is True
    assert status["resident_models"]["iVAD"] is True
    assert status["resident_models"]["iLangID"] is True
    assert status["resident_models"]["iASR"] is True
    assert status["resident_models"]["iTranslate"] is True
    assert status["resident_models"]["iBrain"] is True
    assert status["resident_models"]["iVoice"] is True
    assert len(status["supported_languages"]) >= 10


class ServerAPITestCase(AioHTTPTestCase):
    async def get_application(self):
        return create_app()

    async def test_get_status(self):
        resp = await self.client.request("GET", "/api/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["offline_ready"] is True
        assert data["is_initialized"] is True

    async def test_post_translate(self):
        payload = {
            "text": "flood evacuation",
            "source_lang": "en",
            "target_lang": "hi"
        }
        resp = await self.client.request("POST", "/api/translate", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert "बाढ़ का पानी बढ़ रहा है" in data["translated_text"]

    async def test_post_brain(self):
        payload = {
            "text": "बाढ़ का पानी आ गया है",
            "language": "hi"
        }
        resp = await self.client.request("POST", "/api/brain", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert "response_text" in data
        assert len(data["response_text"]) > 0

    async def test_post_tts(self):
        payload = {
            "text": "नमस्ते, आई-तंत्रा तैयार है।",
            "language": "hi"
        }
        resp = await self.client.request("POST", "/api/tts", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
