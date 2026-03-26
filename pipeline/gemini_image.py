"""Nano Banana (Gemini native image) generation via google.genai."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any, List, Optional, Union

from PIL import Image
from google.genai.types import GenerateContentConfig, Modality

from . import config


def _client():
    from google import genai

    return genai.Client(api_key=config.google_api_key())


def _load_image(path: Union[str, Path]) -> Image.Image:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    return Image.open(p).convert("RGB")


def generate_image_bytes(
    prompt: str,
    image_inputs: Optional[List[Union[str, Path, Image.Image]]] = None,
    model: Optional[str] = None,
) -> bytes:
    """
    Text + optional reference images -> one output image (PNG bytes).
    """
    model = model or config.image_model()
    client = _client()
    contents: List[Any] = [prompt]
    for item in image_inputs or []:
        if isinstance(item, Image.Image):
            contents.append(item)
        else:
            contents.append(_load_image(item))

    gen_cfg = GenerateContentConfig(
        response_modalities=[Modality.TEXT, Modality.IMAGE],
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=gen_cfg,
    )

    if not response.candidates:
        raise RuntimeError("Gemini returned no candidates")

    parts = response.candidates[0].content.parts
    for part in parts:
        if hasattr(part, "inline_data") and part.inline_data is not None:
            data = part.inline_data.data
            if isinstance(data, bytes):
                return data
            if isinstance(data, str):
                return base64.b64decode(data)
        if hasattr(part, "as_image") and callable(part.as_image):
            pil = part.as_image()
            if pil is not None:
                buf = io.BytesIO()
                pil.save(buf, format="PNG")
                return buf.getvalue()

    raise RuntimeError("No image data in Gemini response")
