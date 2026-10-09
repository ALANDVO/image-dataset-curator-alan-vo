"""
LLM integration service: opt-in advisory descriptions for images and datasets.

Supports OpenAI-compatible, Anthropic messages, and Gemini generateContent APIs.
All calls are bounded by timeout; errors are redacted in responses.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..core.config import settings


def _redact_key(text: str) -> str:
    """Remove any credential-shaped strings from error messages."""
    # Replace anything that looks like a bearer token or API key
    text = re.sub(r"sk-[A-Za-z0-9\-_]{8,}", "sk-<redacted>", text)
    text = re.sub(r"Bearer [A-Za-z0-9\-_.]{8,}", "Bearer <redacted>", text)
    return text


async def _call_openai_compatible(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


async def _call_anthropic(prompt: str) -> str:
    headers = {
        "x-api-key": settings.LLM_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.LLM_MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["content"][0]["text"].strip()


async def _call_gemini(prompt: str) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.LLM_MODEL}:generateContent?key={settings.LLM_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def get_llm_advisory(
    prompt: str,
) -> dict[str, Any]:
    """
    Call the configured LLM provider and return an advisory result.

    Returns {"text": ..., "provider": ..., "model": ...} on success.
    Returns {"error": ..., "advisory": true} on failure (never fabricates).
    This result must be labeled advisory in the UI.
    """
    if not settings.LLM_API_KEY:
        return {
            "error": "LLM_API_KEY not configured; advisory unavailable.",
            "advisory": True,
        }

    provider = settings.LLM_PROVIDER.lower()
    try:
        if provider == "anthropic":
            text = await _call_anthropic(prompt)
        elif provider == "gemini":
            text = await _call_gemini(prompt)
        else:
            # openai-compatible (default; covers OpenRouter, LiteLLM, Ollama, etc.)
            text = await _call_openai_compatible(prompt)
        return {
            "text": text,
            "provider": provider,
            "model": settings.LLM_MODEL,
            "advisory": True,
        }
    except Exception as exc:
        err_msg = _redact_key(str(exc))
        return {"error": f"LLM call failed: {err_msg}", "advisory": True}


async def describe_image_advisory(
    filename: str,
    width: int | None,
    height: int | None,
    labels: list[str],
    exif_issues: list[dict[str, str]],
) -> dict[str, Any]:
    """Build an advisory description for a single image based on its metadata."""
    issues_text = (
        ", ".join(i["tag"] for i in exif_issues) if exif_issues else "none"
    )
    labels_text = ", ".join(labels) if labels else "unlabeled"
    prompt = (
        f"You are a computer-vision dataset assistant. Briefly (2–3 sentences) describe "
        f"what is known about this image from its metadata:\n"
        f"- Filename: {filename}\n"
        f"- Dimensions: {width}x{height}\n"
        f"- Labels: {labels_text}\n"
        f"- EXIF privacy issues: {issues_text}\n"
        f"Focus on dataset quality and curation advice. Do not invent content."
    )
    return await get_llm_advisory(prompt)


async def describe_dataset_advisory(
    name: str,
    total: int,
    duplicate_count: int,
    exif_issues_count: int,
    split_stats: dict[str, int],
    labels: list[str],
) -> dict[str, Any]:
    """Build an advisory quality summary for a dataset."""
    splits = ", ".join(f"{k}={v}" for k, v in split_stats.items())
    labels_text = ", ".join(labels) if labels else "unlabeled"
    prompt = (
        f"You are a computer-vision dataset assistant. Briefly (3–4 sentences) assess the "
        f"curation quality of the dataset '{name}':\n"
        f"- Total images: {total}\n"
        f"- Detected duplicates: {duplicate_count}\n"
        f"- Images with EXIF privacy issues: {exif_issues_count}\n"
        f"- Split distribution: {splits}\n"
        f"- Label vocabulary: {labels_text}\n"
        f"Focus on potential bias, class imbalance, and privacy risks. Do not invent data."
    )
    return await get_llm_advisory(prompt)
