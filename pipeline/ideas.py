"""Campaign ideas generator — mines customer reviews for email campaign angles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, gemini_text


_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "ideas.system.md"


def run(
    product_focus: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Generate email campaign ideas from customer reviews + brand identity.

    Args:
        product_focus: Optional filter — "beef_crisps", "pork_crisps", "crispy_beef_bits", or None for all
        output_path: If provided, write JSON output to this file

    Returns:
        List of campaign idea dicts
    """
    pc = product_focus if product_focus and product_focus != "all" else None

    review_highlights = gemini_text.load_review_highlights(product_focus=pc, max_chars=8000)
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)
    system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    focus_line = f"Product focus: {product_focus}" if product_focus else "Product focus: all products"
    prompt = f"""{focus_line}

CUSTOMER REVIEWS (verbatim quotes from real buyers):
{review_highlights}

BRAND IDENTITY:
{brand_identity[:6000]}

Generate 6-10 email campaign ideas grounded in these customer insights."""

    raw = gemini_text.generate_text(
        prompt=prompt,
        model=config.brief_model(),
        system=system_prompt,
    )

    # Strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        ideas = json.loads(text)
    except json.JSONDecodeError:
        # Return raw as a single-item list with the parse error
        return [{"parse_error": True, "raw": text}]

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(ideas, indent=2, ensure_ascii=False), encoding="utf-8")

    return ideas


def print_ideas(ideas: List[Dict[str, Any]]) -> None:
    """Pretty-print ideas to stdout."""
    if not ideas:
        print("No ideas generated.")
        return

    if ideas[0].get("parse_error"):
        print("ERROR: Failed to parse LLM response as JSON.")
        print(ideas[0].get("raw", ""))
        return

    print(f"\n{'='*60}")
    print(f"  {len(ideas)} EMAIL CAMPAIGN IDEAS")
    print(f"{'='*60}\n")

    for i, idea in enumerate(ideas, 1):
        print(f"{'─'*60}")
        print(f"  {i}. {idea.get('name', 'Untitled')}")
        print(f"{'─'*60}")
        print(f"  Angle:      {idea.get('angle', '')}")
        print(f"  Inspired by: {idea.get('inspired_by', '')}")
        print(f"  Theme:      {idea.get('email_theme', '')}")
        print(f"  Key msg:    {idea.get('key_message', '')}")
        print(f"  Tone:       {idea.get('suggested_tone', '')}")
        products = idea.get("suggested_products", [])
        if products:
            print(f"  Products:   {', '.join(products)}")
        quotes = idea.get("social_proof_quotes", [])
        if quotes:
            print("  Quotes:")
            for q in quotes:
                print(f"    • \"{q}\"")
        print()
