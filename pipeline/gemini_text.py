"""Gemini text generation (brief, copy, cohesion, etc.)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from google import genai
from google.genai.types import GenerateContentConfig

from . import config


def _client() -> genai.Client:
    return genai.Client(api_key=config.google_api_key())


def generate_text(
    prompt: str,
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """Single-turn text generation."""
    model = model or config.text_model()
    client = _client()
    cfg = None
    if system:
        cfg = GenerateContentConfig(system_instruction=system)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=cfg,
    )
    text = _extract_text(response)
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text.strip()


def generate_text_with_images(
    prompt: str,
    images: List[Any],
    model: Optional[str] = None,
    system: Optional[str] = None,
) -> str:
    """Multimodal: prompt + PIL images."""
    model = model or config.text_model()
    client = _client()
    parts: List[Any] = [prompt]
    parts.extend(images)
    cfg = None
    if system:
        cfg = GenerateContentConfig(system_instruction=system)
    response = client.models.generate_content(
        model=model,
        contents=parts,
        config=cfg,
    )
    text = _extract_text(response)
    if not text:
        raise RuntimeError("Gemini returned empty text")
    return text.strip()


def _extract_text(response: Any) -> str:
    if not response or not getattr(response, "candidates", None):
        return ""
    parts = response.candidates[0].content.parts
    chunks: List[str] = []
    for part in parts:
        if hasattr(part, "text") and part.text:
            chunks.append(part.text)
    return "".join(chunks)


def _is_identity_txt(path: Path) -> bool:
    if path.suffix.lower() != ".txt":
        return False
    if path.name.lower() == "readme.txt":
        return False
    return True


def _concat_txt_folder(folder: Path, label: str) -> str:
    if not folder.is_dir():
        return ""
    texts: List[str] = []
    for path in sorted(folder.glob("*.txt")):
        if not _is_identity_txt(path):
            continue
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    if not texts:
        return ""
    header = f"[{label}]\n"
    return header + "\n\n".join(texts)


_FOCUS_KEYWORDS: dict = {
    "beef_crisps": ["beef crisps", "mild", "spicy", "teriyaki", "sampler", "best seller", "spice lovers"],
    "crispy_beef_bits": ["beef bits"],
    "pork_crisps": ["pork", "habanero"],
}


def load_review_highlights(
    product_focus: Optional[str] = None,
    max_chars: int = 5000,
) -> str:
    """
    Load verbatim customer review quotes from review_highlights.txt.

    If product_focus is given, filters to only the ## sections whose heading
    contains a keyword for that product. Otherwise returns the full file.
    Strips the 4-line header comment block. Truncates to max_chars.
    """
    path = config.review_highlights_path()
    if not path.is_file():
        return ""

    text = path.read_text(encoding="utf-8")

    # Strip leading comment lines (lines starting with #)
    lines = text.splitlines(keepends=True)
    start = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            start = i
            break
    text = "".join(lines[start:]).strip()

    if product_focus and product_focus in _FOCUS_KEYWORDS:
        keywords = _FOCUS_KEYWORDS[product_focus]
        sections = text.split("\n## ")
        # First element may not start with ##
        kept = []
        for i, section in enumerate(sections):
            heading = section.split("\n", 1)[0].lower()
            if i == 0 and not section.startswith("##"):
                # Skip the intro before the first ## heading
                continue
            if any(kw in heading for kw in keywords):
                kept.append(section if section.startswith("##") else "## " + section)
        text = "\n\n".join(kept).strip() if kept else text

    return text[:max_chars]


def load_brand_identity_text(
    product_category: Optional[str] = None,
    flavor: Optional[str] = None,
) -> str:
    """
    Hierarchical brand identity:

    1. Global: identity_text/*.txt (root only)
    2. Category: identity_text/product_categories/<category>/*.txt
    3. Flavor: assets/flavor_identity/<category>/<flavor>/*.txt
    """
    blocks: List[str] = []

    root = config.brand_identity_dir()
    if root.is_dir():
        global_parts: List[str] = []
        for path in sorted(root.glob("*.txt")):
            if not _is_identity_txt(path):
                continue
            try:
                global_parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
        if global_parts:
            blocks.append("[GLOBAL BRAND]\n" + "\n\n".join(global_parts))

    if product_category:
        cat_dir = config.brand_identity_product_categories_dir() / product_category
        cat_block = _concat_txt_folder(cat_dir, f"PRODUCT LINE: {product_category}")
        if cat_block:
            blocks.append(cat_block)

    if product_category and flavor:
        sku_id = config.flavor_identity_dir(product_category, flavor)
        flav_block = _concat_txt_folder(sku_id, f"SKU FLAVOR: {product_category}/{flavor}")
        if flav_block:
            blocks.append(flav_block)

    return "\n\n---\n\n".join(blocks).strip()
