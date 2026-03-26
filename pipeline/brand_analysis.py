"""Brand analysis — extract visual brand guidelines from website screenshots.

Run once (or re-run when new screenshots are added) to produce
brand/identity_text/visual_brand_analysis.txt, which then flows
automatically into every pipeline step via load_brand_identity_text().
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PIL import Image

from . import config, gemini_text


ANALYSIS_PROMPT = """You are a brand strategist analysing website screenshots to extract actionable visual brand guidelines for an email design system.

Analyse the provided screenshots carefully and produce a structured brand guide under these exact headings. Be specific and concrete — include hex codes, font weight names, example phrases, and pixel-level observations where possible.

## COLOR PALETTE
List all colors you can identify:
- Primary colors (hex, usage context)
- Secondary/accent colors (hex, usage context)
- Background colors used
- Text colors used
- CTA button colors (background + text)

## TYPOGRAPHY STYLE
Describe the typographic character:
- Heading style (weight, case, letter-spacing, feel)
- Body text style
- CTA/button text style
- Any distinctive type treatments (gradients, outlines, mixed case etc.)
- Overall typographic personality (bold/minimal/playful/premium etc.)

## LAYOUT & SPACING
- Overall density (spacious / balanced / dense)
- Section padding and whitespace approach
- Grid structure observations
- How content is visually grouped

## VISUAL TONE & AESTHETIC
- Overall aesthetic in 3-5 adjectives
- Photography style (if visible): lighting, mood, subject matter
- Illustration or icon style (if present)
- Use of patterns, textures, gradients

## CTA & BUTTON STYLE
- Button shape (rounded corners, pill, square)
- Button size and prominence
- Hover/active state clues if visible
- CTA copy style (imperative verbs? length? energy level?)

## EMAIL DESIGN IMPLICATIONS
Based on the above, write 6-10 specific rules an AI system should follow when generating emails for this brand. Example format:
- "Always use [COLOR] for primary CTA buttons, never [OTHER COLOR]"
- "Headline copy should be [STYLE], not [ANTI-PATTERN]"
- "Hero images should feel [DESCRIPTOR], avoid [ANTI-PATTERN]"

Be direct and opinionated. These rules will be injected verbatim into AI prompts."""


def _load_images(folder: Path) -> List[Image.Image]:
    exts = (".png", ".jpg", ".jpeg", ".webp")
    paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in exts and not p.name.startswith("."))
    if not paths:
        raise FileNotFoundError(f"No images found in {folder}")
    images = []
    for p in paths:
        img = Image.open(p).convert("RGB")
        # Downscale very large screenshots to keep token cost reasonable
        max_dim = 1800
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        images.append(img)
    return images


def run(
    inspo_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    model: Optional[str] = None,
) -> Path:
    """
    Analyse screenshots in inspo_dir, write brand guide to output_path.

    Defaults:
      inspo_dir   → brand/website/
      output_path → brand/identity_text/visual_brand_analysis.txt
    """
    if inspo_dir is None:
        inspo_dir = config.root().parent / "brand" / "website"
    if output_path is None:
        output_path = config.brand_identity_dir() / "visual_brand_analysis.txt"

    inspo_dir = Path(inspo_dir)
    output_path = Path(output_path)

    images = _load_images(inspo_dir)
    n = len(images)
    print(f"  Loaded {n} screenshot{'s' if n != 1 else ''} from {inspo_dir}")

    # Use a capable vision model — default to gemini-2.5-pro
    vision_model = model or "gemini-2.5-pro"

    print(f"  Analysing with {vision_model}...")
    analysis = gemini_text.generate_text_with_images(
        prompt=ANALYSIS_PROMPT,
        images=images,
        model=vision_model,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Visual Brand Analysis\n"
        f"# Generated from: {inspo_dir}\n"
        f"# Screenshots analysed: {n}\n"
        "# Re-run `python main.py brand-analysis` to refresh after adding new screenshots.\n\n"
    )
    output_path.write_text(header + analysis, encoding="utf-8")

    return output_path
