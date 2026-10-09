"""Tests for LLM service: mocked provider calls, redaction, no real credentials."""
from __future__ import annotations

import os
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


class TestLLMServiceRedaction:
    def test_no_api_key_returns_error_not_fabricated(self):
        """Without LLM_API_KEY, advisory returns error, not fabricated response."""
        import asyncio
        from app.services.llm_service import get_llm_advisory
        # Ensure no key is set
        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.LLM_API_KEY = ""
            result = asyncio.get_event_loop().run_until_complete(get_llm_advisory("test prompt"))
        assert "error" in result
        assert result.get("advisory") is True
        assert "text" not in result

    def test_redact_key_removes_credential_like_strings(self):
        from app.services.llm_service import _redact_key
        # Generate a synthetic key-shaped string (provider prefix + repeated zeros, never a real key)
        synthetic = "sk-" + "0" * 48
        result = _redact_key(f"Error: {synthetic}")
        assert "sk-<redacted>" in result
        assert "0" * 48 not in result

    def test_redact_bearer_token(self):
        from app.services.llm_service import _redact_key
        synthetic_bearer = "Bearer " + "0" * 32
        result = _redact_key(f"Unauthorized: {synthetic_bearer}")
        assert "Bearer <redacted>" in result

    @pytest.mark.asyncio
    async def test_openai_compatible_mocked(self):
        """Mocked OpenAI-compatible call returns advisory text."""
        from app.services.llm_service import get_llm_advisory
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Advisory text here."}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.llm_service.settings") as mock_settings:
            mock_settings.LLM_API_KEY = "sk-" + "0" * 20  # synthetic
            mock_settings.LLM_PROVIDER = "openai-compatible"
            mock_settings.LLM_MODEL = "gpt-4o-mini"
            mock_settings.LLM_BASE_URL = "https://api.example.com/v1"

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                result = await get_llm_advisory("test prompt")

        assert result.get("text") == "Advisory text here."
        assert result.get("advisory") is True
