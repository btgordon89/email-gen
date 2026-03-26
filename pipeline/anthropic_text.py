"""Anthropic Claude text generation (drop-in alternative to gemini_text)."""

from __future__ import annotations

import os
from typing import List, Optional

import anthropic

from . import config


def _client() -> anthropic.Anthropic:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ValueError("Set ANTHROPIC_API_KEY in .env to use Anthropic models")
    return anthropic.Anthropic(api_key=key)


def generate_text(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """Single-turn text generation via Anthropic Claude."""
    model = model or config.text_model()
    client = _client()

    kwargs = {
        "model": model,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = _extract_text(response)
    if not text:
        raise RuntimeError("Anthropic returned empty text")
    return text.strip()


def generate_text_with_images(
    prompt: str,
    images: List,
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """Multimodal: prompt + PIL images via Anthropic Claude."""
    import base64
    import io

    model = model or config.text_model()
    client = _client()

    content: List = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": b64},
        })
    content.append({"type": "text", "text": prompt})

    kwargs = {
        "model": model,
        "max_tokens": 8096,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = _extract_text(response)
    if not text:
        raise RuntimeError("Anthropic returned empty text")
    return text.strip()


def _extract_text(response) -> str:
    chunks = []
    for block in response.content:
        if hasattr(block, "text") and block.text:
            chunks.append(block.text)
    return "".join(chunks)
