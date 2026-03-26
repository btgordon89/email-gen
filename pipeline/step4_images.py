"""Step 4: Image generation — raster assets + alt text for image-agent tokens.

REFACTORED STRATEGY:
- Product shots: Use Shopify photos directly (download, no generation)
- Lifestyle/scene images: ONLY generate if brand reference images exist
- NEVER generate without reference images
- Track everything in detailed audit logs
"""

from __future__ import annotations

import base64
import hashlib
import io as _io
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from . import anthropic_text, config, effective, gemini_image, gemini_text, io_util, questionnaire as questionnaire_module


def _generate_text(prompt: str, model: str, system: str) -> str:
    if model.startswith("claude-"):
        return anthropic_text.generate_text(prompt=prompt, model=model, system=system)
    return gemini_text.generate_text(prompt=prompt, model=model, system=system)

ALT_SYSTEM = """You write concise email image alt text for accessibility and screen readers.
Rules:
- Max 125 characters per value
- Describe what is shown, not marketing fluff
- No phrases like "image of" or "picture of"
Output valid JSON only, no markdown. Keys must be the exact token strings provided (including curly braces)."""


def _token_inner(token: str) -> str:
    return token.replace("{{", "").replace("}}", "").strip()


def _is_alt_token(token: str) -> bool:
    return _token_inner(token).endswith("_alt")


def _first_brand_logo_file() -> Optional[Path]:
    d = config.brand_logo_dir()
    if not d.is_dir():
        return None
    exts = (".png", ".jpg", ".jpeg", ".webp", ".svg")
    found: List[Path] = []
    for ext in exts:
        found.extend(p for p in d.glob(f"*{ext}") if p.is_file())
    return sorted(found)[0] if found else None


def _spotlight_slug(inner: str) -> Optional[str]:
    m = re.match(r"^product_spotlight_(.+)_image$", inner)
    return m.group(1) if m else None


def _match_featured_by_slug(products: List[Dict[str, Any]], slug: str) -> Optional[Dict[str, Any]]:
    slug_l = slug.lower().replace("-", "_")
    for p in products:
        handle = str(p.get("handle") or "").lower()
        if not handle:
            continue
        if slug_l in handle or handle.startswith(slug_l) or slug_l in handle.replace("-", "_"):
            return p
    return None


def _find_website_inspo_images(max_images: int = 4) -> List[Path]:
    """
    Return up to max_images website screenshot paths from brand/website/.
    These are used as visual style reference for hero image generation.
    """
    inspo_dir = config.brand_website_inspo_dir()
    if not inspo_dir.is_dir():
        return []
    exts = (".png", ".jpg", ".jpeg", ".webp")
    found = sorted(p for p in inspo_dir.iterdir() if p.suffix.lower() in exts and not p.name.startswith("."))
    return found[:max_images]


def _find_brand_product_images(category: str, flavor: Optional[str] = None) -> List[Path]:
    """
    Find product reference images from brand/assets/product_images.
    Returns lifestyle shots showing the product in use.
    """
    brand_root = config.root().parent / "brand" / "assets" / "product_images"
    if not brand_root.is_dir():
        return []
    
    found: List[Path] = []
    category_dir = brand_root / category
    
    if not category_dir.is_dir():
        return []
    
    # If flavor specified, look in that flavor folder
    if flavor:
        flavor_dir = category_dir / flavor.lower()
        if flavor_dir.is_dir():
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                found.extend(p for p in flavor_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    # Also check for category-level images (not in flavor subfolders)
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        found.extend(p for p in category_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    # If no flavor-specific images, get all images from all flavors
    if not found and not flavor:
        for flavor_dir in category_dir.iterdir():
            if flavor_dir.is_dir() and not flavor_dir.name.startswith("."):
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    found.extend(p for p in flavor_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    return sorted(found)


def _infer_flavor(title: str, handle: str) -> Optional[str]:
    """Infer flavor folder name from product title or handle."""
    text = (title + " " + handle).lower()
    if "honey" in text and "butter" in text:
        return "honey_butter"
    if "honey" in text:
        return "honey_butter"
    if "teriyaki" in text:
        return "teriyaki"
    if "spicy" in text or "spice" in text:
        return "spicy"
    if "original" in text or "mild" in text:
        return "original"
    return None


def _ensure_shopify_bag_images(category: str, featured: List[Dict[str, Any]]) -> None:
    """
    Download each featured product's Shopify hero image into
    bag_images/{category}/{flavor}/ if that folder is empty.
    Persists across runs so subsequent runs use the cached images.
    """
    bag_root = config.root().parent / "brand" / "assets" / "bag_images"
    for prod in featured:
        url = prod.get("primary_image_url")
        if not url:
            continue
        flavor = _infer_flavor(prod.get("title", ""), prod.get("handle", ""))
        dest_dir = (bag_root / category / flavor) if flavor else (bag_root / category)
        dest_dir.mkdir(parents=True, exist_ok=True)
        existing = [
            p for p in dest_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and p.is_file()
        ]
        if not existing:
            ext = _extension_from_url_or_ct(str(url), None)
            try:
                _download_url(str(url), dest_dir / f"shopify_hero{ext}")
            except Exception:
                pass  # non-fatal — generation will skip if still empty


def _find_brand_bag_images(category: str, flavor: Optional[str] = None) -> List[Path]:
    """
    Find bag/packaging images from brand/assets/bag_images.
    Returns product packaging shots.
    """
    brand_root = config.root().parent / "brand" / "assets" / "bag_images"
    if not brand_root.is_dir():
        return []
    
    found: List[Path] = []
    category_dir = brand_root / category
    
    if not category_dir.is_dir():
        # Check for generic bag images at root level
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            found.extend(p for p in brand_root.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
        return sorted(found)
    
    # If flavor specified, look in that flavor folder
    if flavor:
        flavor_dir = category_dir / flavor.lower()
        if flavor_dir.is_dir():
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                found.extend(p for p in flavor_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    # Also check for category-level images
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        found.extend(p for p in category_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    # If no flavor-specific images, get all images from all flavors
    if not found and not flavor:
        for flavor_dir in category_dir.iterdir():
            if flavor_dir.is_dir() and not flavor_dir.name.startswith("."):
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    found.extend(p for p in flavor_dir.glob(f"*{ext}") if p.is_file() and not p.name.startswith("."))
    
    return sorted(found)


def _is_product_shot_token(inner: str) -> bool:
    """
    Determine if this token represents a pure product shot that should use
    Shopify photos directly (no generation).
    """
    return (
        inner.startswith("product_spotlight_") and inner.endswith("_image")
        or re.match(r"^product_\d+_image$", inner) is not None
        or inner == "product_feature_sampler_image"
        or inner.endswith("_product_image")
        or inner.endswith("_highlight_image")
        or inner.endswith("_feature_image")
        or (inner.endswith("_image") and "product" in inner and not re.match(r"^(hero|banner|usage|lifestyle|benefit)", inner))
    )


def _extension_from_url_or_ct(url: str, content_type: Optional[str]) -> str:
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if "jpeg" in ct or "jpg" in ct:
            return ".jpg"
        if "png" in ct:
            return ".png"
        if "webp" in ct:
            return ".webp"
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _download_url(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    dest.write_bytes(r.content)


def _parse_alt_json(response: str, expected_tokens: List[str]) -> Dict[str, str]:
    text = response.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start < end:
            block = text[start + 3 : end].strip()
            if block.startswith("json"):
                block = block[4:].lstrip()
            text = block
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    out: Dict[str, str] = {}
    for tok in expected_tokens:
        v = data.get(tok)
        if isinstance(v, str) and v.strip():
            out[tok] = v.strip()[:125]
    return out


def _generate_alts(
    manifest: List[Dict[str, Any]],
    brief: Dict[str, Any],
    copy: Dict[str, Any],
    brand_identity: str,
) -> Dict[str, str]:
    alt_entries = [t for t in manifest if t.get("source_agent") == "image" and _is_alt_token(t.get("token", ""))]
    if not alt_entries:
        return {}

    token_list = [t["token"] for t in alt_entries]
    desc = json.dumps(
        [{"token": t["token"], "description": t.get("description", "")} for t in alt_entries],
        indent=2,
    )
    copy_bits = json.dumps(
        {
            "subject_line": copy.get("subject_line", ""),
            "sample_copy": dict(list((copy.get("copy_by_token") or {}).items())[:12]),
        },
        indent=2,
    )

    prompt = f"""Write alt text for these email image tokens.

CAMPAIGN / BRIEF (context):
{brief.get('creative_concept', '')[:2000]}

TOKEN DEFINITIONS:
{desc}

NEARBY COPY (for tone consistency):
{copy_bits[:4000]}

BRAND (short):
{brand_identity[:1500]}

Return a JSON object with exactly these keys (same spelling, including {{{{}}}}):
{json.dumps(token_list)}
"""

    raw = _generate_text(
        prompt=prompt,
        model=config.text_model(),
        system=ALT_SYSTEM,
    )
    parsed = _parse_alt_json(raw, token_list)
    # Fallback: use manifest description truncated
    for t in alt_entries:
        tok = t["token"]
        if tok not in parsed:
            parsed[tok] = (t.get("description") or "Campaign image")[:125]
    return parsed


# Variation pools for hero image generation — each email draws a different combination
_HERO_SUBJECTS = [
    "Asian-style noodle bowl with vibrant colorful toppings; Crispy Beef Bits as the signature crunchy garnish piled in the center.",
    "Fresh mixed salad bowl (leafy greens, cucumber ribbons, shaved radish, shredded carrot) with Crispy Beef Bits scattered generously across the top.",
    "Korean-inspired bibimbap: white rice, vivid vegetable sections arranged by color, sesame seeds, and a heap of Crispy Beef Bits crowning the bowl.",
    "Grain bowl (farro or quinoa base) with roasted sweet potato, sliced avocado, microgreens, and Crispy Beef Bits as the crunchy finishing layer.",
    "Thai-style glass noodle salad with fresh mint, cilantro, thinly sliced chili, lime wedges on the side, and Crispy Beef Bits throughout.",
    "Relaxed brunch spread — multiple small sharing plates, small condiment bowls, and Crispy Beef Bits as the featured topping in the foreground.",
    "Vibrant poke bowl on a sunlit kitchen counter — marinated protein, pickled vegetables, sesame, with Crispy Beef Bits as the unmissable crunchy finish.",
    "Ramen-style bowl with rich-looking broth, springy wavy noodles, a halved soft-boiled egg, and Crispy Beef Bits floating on the surface.",
]

_HERO_ANGLES = [
    "COMPOSITION: Shoot straight overhead — 100% top-down flat-lay. Table surface or linen texture visible around the dish edges. Graphic, geometric, editorial.",
    "COMPOSITION: Shoot at a classic 45-degree food photography angle. Apply shallow depth-of-field with background bokeh. Timeless and appetizing.",
    "COMPOSITION: Shoot fully at eye level — horizontal side profile. Emphasize height, layers, and depth inside the bowl. Immersive and dramatic.",
    "COMPOSITION: Shoot at a 30-degree three-quarter angle. Place the dish slightly off-center with breathing room. Relaxed, lifestyle feel.",
    "COMPOSITION: Extreme close-up / macro style. Fill 75% of the frame with the food detail; Crispy Beef Bits texture is prominent and tactile.",
]

_HERO_LIGHTS = [
    "LIGHTING: Bright natural side-light streaming in from a window on the left. Soft directional shadows add warmth and depth.",
    "LIGHTING: Overhead diffused daylight — even, clean, shadow-free illumination. Bright and vibrant.",
    "LIGHTING: Warm golden-hour tones, slightly warm white balance. Inviting, cozy, editorial lifestyle feel.",
    "LIGHTING: Crisp neutral studio-style white light. High-contrast, clean, and editorial.",
    "LIGHTING: Soft backlight with a gentle rim glow around the dish. Fresh, summery, and ethereal.",
]


def _hero_prompt(
    brief: Dict[str, Any],
    questionnaire: Dict[str, Any],
    identity: str,
    email_num: int = 1,
    total_emails: int = 1,
    description: str = "",
) -> str:
    # Deterministic variation: different emails/themes get distinct subject+angle+lighting combos
    seed_text = (
        str(email_num)
        + (questionnaire.get("email_theme") or "")[:80]
        + (brief.get("creative_concept") or "")[:80]
    )
    seed = int(hashlib.md5(seed_text.encode()).hexdigest(), 16)

    subject = _HERO_SUBJECTS[seed % len(_HERO_SUBJECTS)]
    angle = _HERO_ANGLES[(seed >> 4) % len(_HERO_ANGLES)]
    lighting = _HERO_LIGHTS[(seed >> 8) % len(_HERO_LIGHTS)]

    seq_angle = (brief.get("angle") or "").strip()

    lines = [
        "Create a wide hero photograph for an email header (landscape, ~3:1 or 2:1 aspect ratio).",
        "",
        f"SUBJECT: {subject}",
        "",
        angle,
        "",
        lighting,
        "",
    ]

    if description:
        lines += [
            "SCENE VISION (from campaign brief — honor this intent):",
            description[:600],
            "",
        ]

    if seq_angle:
        lines += [
            "EMAIL ANGLE (let this inform the mood and energy of the shot):",
            seq_angle[:400],
            "",
        ]

    lines += [
        "CRITICAL RULES:",
        "- Absolutely NO text, NO logos, NO branding, NO watermarks anywhere in the image.",
        "- NO product packaging with visible labels (bags/packages must not appear).",
        "- Generate ONLY the food photography scene. The brand logo will be overlaid separately in HTML.",
        "",
        "CREATIVE DIRECTION:",
        (brief.get("creative_concept") or "")[:2500],
        "",
        "THEME:",
        str(questionnaire.get("email_theme", ""))[:500],
        "",
        "BRAND CONTEXT:",
        identity[:4000],
    ]

    return "\n".join(lines)


def _icon_prompt(benefit_idx: int, description: str, benefit_text: str, identity: str) -> str:
    return "\n".join(
        [
            f"Create a simple, flat icon for benefit #{benefit_idx} in a promotional email.",
            "Style: minimal vector-like illustration, 512x512, bold shapes, 2-4 colors.",
            f"Brand palette hints: navy #2c5f7f, gold #FFB800, accent red #D32F2F. Light or white background.",
            "No text, no letters, no watermarks.",
            "",
            f"Manifest hint: {description}",
            f"Benefit copy (concept): {benefit_text[:200]}",
            "",
            identity[:1500],
        ]
    )


def _hash_text(text: str) -> str:
    """Compute SHA256 hash of text (for change detection)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n[... truncated ...]"


def _thumb_b64(path: Path, max_px: int = 240) -> Optional[str]:
    """Return a base64 JPEG thumbnail data URI, or None if unavailable."""
    try:
        from PIL import Image as _PILImage  # optional — PIL is in requirements
        img = _PILImage.open(path).convert("RGB")
        img.thumbnail((max_px, max_px), _PILImage.LANCZOS)
        buf = _io.BytesIO()
        img.save(buf, format="JPEG", quality=78)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _write_html_audit_report(
    run_dir: Path,
    image_generations: List[Dict[str, Any]],
    total_duration_seconds: float,
    model: str,
    email_num: int = 1,
    total_emails: int = 1,
) -> None:
    """Write a visual HTML audit report showing all generated images with prompts and reference thumbnails."""
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(exist_ok=True)

    suffix = f"_email_{email_num}" if total_emails > 1 else ""
    html_path = audit_dir / f"step4_images{suffix}.audit.html"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    email_label = f" — Email {email_num}/{total_emails}" if total_emails > 1 else ""
    campaign_name = run_dir.name

    METHOD_COLOR = {
        "generated": "#2563eb",
        "downloaded": "#16a34a",
        "copied": "#7c3aed",
        "skipped": "#dc2626",
    }

    cards: List[str] = []
    for gen in image_generations:
        token = gen.get("token", "")
        method = gen.get("generation_method") or "error"
        color = METHOD_COLOR.get(method, "#6b7280")
        dur = gen.get("duration_seconds", 0)
        error = gen.get("error") or ""
        prompt = gen.get("prompt") or ""
        refs = gen.get("reference_images") or []
        output_path = gen.get("output_path")
        desc = gen.get("token_description") or ""

        # Output image thumbnail — embed as base64 for portability
        out_img_html = '<div class="no-img">No output</div>'
        if output_path:
            out_abs = run_dir / output_path
            thumb = _thumb_b64(out_abs, max_px=700)
            if thumb:
                out_img_html = f'<img class="out-img" src="{thumb}" alt="{token}">'

        # Reference image thumbnails
        ref_html = ""
        if refs:
            items: List[str] = []
            for rp in refs:
                rabs = Path(rp) if Path(rp).is_absolute() else config.root().parent / rp
                rname = Path(rp).name
                rt = _thumb_b64(rabs, max_px=200)
                if rt:
                    items.append(
                        f'<div class="ref-item" title="{rp}">'
                        f'<img class="ref-thumb" src="{rt}" alt="{rname}">'
                        f'<div class="ref-label">{rname}</div></div>'
                    )
                else:
                    items.append(
                        f'<div class="ref-item ref-miss" title="{rp}">'
                        f'<div class="ref-label">{rname}</div></div>'
                    )
            ref_html = (
                '<div class="refs"><h4>Reference images sent to Gemini</h4>'
                '<div class="ref-grid">' + "".join(items) + "</div></div>"
            )

        prompt_html = ""
        if prompt:
            esc = prompt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            prompt_html = (
                '<details class="prompt-wrap"><summary>Prompt sent to Gemini</summary>'
                f'<pre class="prompt">{esc}</pre></details>'
            )

        err_html = f'<div class="err">Error: {error}</div>' if error else ""
        desc_html = f'<div class="desc">{desc}</div>' if desc else ""

        cards.append(f"""
<div class="card">
  <div class="ch" style="border-left:4px solid {color}">
    <code class="tok">{token}</code>
    <span class="badge" style="background:{color}">{method}</span>
    <span class="dur">{dur:.1f}s</span>
  </div>
  {desc_html}
  {out_img_html}
  {err_html}
  {ref_html}
  {prompt_html}
</div>""")

    n_gen = sum(1 for g in image_generations if g.get("generation_method") == "generated")
    n_dl = sum(1 for g in image_generations if g.get("generation_method") == "downloaded")
    n_cp = sum(1 for g in image_generations if g.get("generation_method") == "copied")
    n_sk = sum(1 for g in image_generations if g.get("generation_method") == "skipped")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Image Audit — {campaign_name}{email_label}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f8fafc;color:#1e293b;margin:0;padding:20px}}
h1{{font-size:1.4rem;margin-bottom:4px}}
.meta{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:24px}}
.stat{{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 16px;font-size:.85rem}}
.stat strong{{display:block;font-size:1.3rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(460px,1fr));gap:20px}}
.card{{background:#fff;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden}}
.ch{{padding:10px 14px;background:#f8fafc;display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.tok{{font-size:.85rem;font-weight:600;flex:1;min-width:0;overflow-wrap:anywhere}}
.badge{{color:#fff;padding:2px 8px;border-radius:12px;font-size:.72rem;font-weight:700;white-space:nowrap}}
.dur{{color:#94a3b8;font-size:.75rem;white-space:nowrap}}
.desc{{padding:4px 14px 6px;color:#64748b;font-size:.78rem;font-style:italic}}
.out-img{{width:100%;height:210px;object-fit:cover;display:block}}
.no-img{{height:60px;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:.85rem;background:#f1f5f9}}
.err{{padding:6px 14px;color:#dc2626;font-size:.82rem;background:#fef2f2}}
.refs{{padding:10px 14px 4px}}
.refs h4{{margin:0 0 6px;font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.ref-grid{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}}
.ref-item{{text-align:center}}
.ref-thumb{{width:72px;height:72px;object-fit:cover;border-radius:4px;border:1px solid #e2e8f0;display:block}}
.ref-label{{font-size:.58rem;color:#94a3b8;max-width:72px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ref-miss{{width:72px;height:72px;background:#f1f5f9;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:.6rem;color:#94a3b8}}
.prompt-wrap{{padding:0 14px 12px}}
.prompt-wrap summary{{cursor:pointer;font-size:.78rem;color:#3b82f6;padding:4px 0}}
.prompt{{font-size:.72rem;background:#f8fafc;border:1px solid #e2e8f0;border-radius:4px;padding:8px;white-space:pre-wrap;word-break:break-word;max-height:280px;overflow-y:auto;margin:6px 0 0}}
</style>
</head>
<body>
<h1>Image Generation Audit — {campaign_name}{email_label}</h1>
<div class="meta">{timestamp} &nbsp;·&nbsp; {model} &nbsp;·&nbsp; {total_duration_seconds:.1f}s total</div>
<div class="stats">
  <div class="stat"><strong>{n_gen}</strong>Generated</div>
  <div class="stat"><strong>{n_dl}</strong>Downloaded</div>
  <div class="stat"><strong>{n_cp}</strong>Copied</div>
  <div class="stat"><strong>{n_sk}</strong>Skipped</div>
</div>
<div class="grid">{"".join(cards)}</div>
</body>
</html>"""

    html_path.write_text(html, encoding="utf-8")


def _write_image_audit_log(
    run_dir: Path,
    image_generations: List[Dict[str, Any]],
    total_duration_seconds: float,
    model: str,
    email_num: int = 1,
    total_emails: int = 1,
    alt_text_generation: Optional[Dict[str, Any]] = None,
) -> None:
    """Write detailed audit log for image generation step."""
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(exist_ok=True)

    audit_record = {
        "step_id": "step4_images",
        "email_num": email_num,
        "total_emails": total_emails,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image_model": model,
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_images_generated": len([g for g in image_generations if g.get("generation_method") == "generated"]),
        "total_images_downloaded": len([g for g in image_generations if g.get("generation_method") == "downloaded"]),
        "total_images_copied": len([g for g in image_generations if g.get("generation_method") == "copied"]),
        "total_images_skipped": len([g for g in image_generations if g.get("generation_method") == "skipped"]),
        "image_generations": image_generations,
        "alt_text_generation": alt_text_generation,
    }

    suffix = f"_email_{email_num}" if total_emails > 1 else ""
    audit_path = audit_dir / f"step4_images{suffix}.audit.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_record, f, indent=2, ensure_ascii=False)

    # Write the visual HTML audit alongside the JSON
    _write_html_audit_report(
        run_dir=run_dir,
        image_generations=image_generations,
        total_duration_seconds=total_duration_seconds,
        model=model,
        email_num=email_num,
        total_emails=total_emails,
    )


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    start_time = time.time()

    full_brief = io_util.read_json(run_dir / io_util.STEP1)
    # Extract per-email brief section in sequence mode
    if total_emails > 1:
        emails = full_brief.get("emails") or []
        idx = email_num - 1
        brief = emails[idx] if 0 <= idx < len(emails) else full_brief
    else:
        brief = full_brief

    structure = effective.effective_structure(run_dir, email_num, total_emails)
    products_data = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2C, email_num, total_emails)
    )
    copy = effective.effective_copy(run_dir, email_num, total_emails)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    focus = questionnaire.get("product_focus", "")
    pc = focus if focus not in ("all", "") else None
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)

    manifest = structure.get("token_manifest") or []
    image_slots = [t for t in manifest if t.get("source_agent") == "image" and not _is_alt_token(t.get("token", ""))]

    # Use per-email subdirectory in sequence mode
    images_subdir = f"email_{email_num}" if total_emails > 1 else None
    images_dir = run_dir / "images" / images_subdir if images_subdir else run_dir / "images"
    images_rel_prefix = f"images/{images_subdir}/" if images_subdir else "images/"
    images_dir.mkdir(parents=True, exist_ok=True)

    alts_by_token = _generate_alts(manifest, brief, copy, brand_identity)

    images_by_token: Dict[str, str] = {}
    assets: List[Dict[str, Any]] = []
    errors: List[str] = []
    audit_generations: List[Dict[str, Any]] = []

    featured = products_data.get("featured_products") or []
    copy_tokens = copy.get("copy_by_token") or {}

    model = config.image_model()

    # Pre-load brand reference images for the product category
    category = focus if focus not in ("all", "") else "crispy_beef_bits"
    brand_product_refs = _find_brand_product_images(category)
    brand_bag_refs = _find_brand_bag_images(category)
    website_inspo_refs = _find_website_inspo_images()
    
    # Download Shopify photos for all featured products
    shopify_product_photos: Dict[str, Path] = {}
    for prod in featured:
        if prod.get("primary_image_url"):
            handle = prod.get("handle", "unknown")
            ext = _extension_from_url_or_ct(str(prod["primary_image_url"]), None)
            dest = images_dir / f"_shopify_{handle}{ext}"
            try:
                if not dest.exists():  # Don't re-download if already exists
                    _download_url(str(prod["primary_image_url"]), dest)
                shopify_product_photos[handle] = dest
            except Exception as e:
                errors.append(f"shopify_download_{handle}: {e}")

    # Populate bag_images from Shopify CDN if local folders are empty, then reload refs
    _ensure_shopify_bag_images(category, featured)
    brand_bag_refs = _find_brand_bag_images(category)

    for entry in image_slots:
        token = entry["token"]
        inner = _token_inner(token)
        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", inner).strip("_") or "image"
        rel = f"{images_rel_prefix}{safe_name}.png"
        dest = run_dir / rel
        
        # Track this generation for audit
        gen_start = time.time()
        audit_record: Dict[str, Any] = {
            "token": token,
            "token_description": entry.get("description", ""),
            "output_path": None,
            "generation_method": None,
            "prompt": None,
            "prompt_hash": None,
            "reference_images": [],
            "source_url": None,
            "source_file": None,
            "duration_seconds": 0,
            "error": None,
        }

        try:
            # LOGO IMAGES: Use hardcoded primary logo
            if "logo" in inner or inner in ("header_logo_image", "header_logo", "header_image", "footer_logo_image"):
                # Hardcoded path to primary brand logo
                logo = config.root().parent / "brand" / "assets" / "brand_logo" / "Primary-01-Beige.png"
                if logo.exists():
                    ext = logo.suffix.lower() or ".png"
                    rel = f"{images_rel_prefix}{safe_name}{ext}"
                    dest = run_dir / rel
                    shutil.copy2(logo, dest)
                    kind = "copied"
                    audit_record["generation_method"] = "copied"
                    audit_record["source_file"] = str(logo.relative_to(config.root().parent))
                else:
                    # Fallback to finding any logo
                    logo = _first_brand_logo_file()
                    if logo:
                        ext = logo.suffix.lower() or ".png"
                        rel = f"{images_rel_prefix}{safe_name}{ext}"
                        dest = run_dir / rel
                        shutil.copy2(logo, dest)
                        kind = "copied"
                        audit_record["generation_method"] = "copied"
                        audit_record["source_file"] = str(logo)
                    else:
                        # No logo available, skip generation
                        errors.append(f"{token}: No brand logo found, skipping")
                        audit_record["generation_method"] = "skipped"
                        audit_record["error"] = "No brand logo file found"
                        audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                        audit_generations.append(audit_record)
                        continue

            # PURE PRODUCT SHOTS: Use Shopify photos directly
            elif _is_product_shot_token(inner):
                matched_photo = None
                
                # Try various matching strategies
                slug = _spotlight_slug(inner) if inner.startswith("product_spotlight_") else None
                if slug:
                    prod = _match_featured_by_slug(featured, slug)
                    if prod and prod.get("handle") in shopify_product_photos:
                        matched_photo = shopify_product_photos[prod["handle"]]
                
                # Try numeric index matching
                m = re.match(r"^product_(\d+)_image$", inner)
                if m and not matched_photo:
                    prod_idx = int(m.group(1))
                    if 0 < prod_idx <= len(featured):
                        prod = featured[prod_idx - 1]
                        if prod.get("handle") in shopify_product_photos:
                            matched_photo = shopify_product_photos[prod["handle"]]
                
                # Try sampler/feature matching
                if ("sampler" in inner.lower() or "feature" in inner.lower()) and not matched_photo:
                    for handle, photo in shopify_product_photos.items():
                        if "sampler" in handle.lower():
                            matched_photo = photo
                            break
                
                # Fallback: use first available Shopify photo when no specific match
                if not matched_photo and shopify_product_photos:
                    matched_photo = next(iter(shopify_product_photos.values()))

                if matched_photo:
                    # Copy the Shopify photo directly
                    ext = matched_photo.suffix
                    rel = f"{images_rel_prefix}{safe_name}{ext}"
                    dest = run_dir / rel
                    shutil.copy2(matched_photo, dest)
                    kind = "downloaded"
                    audit_record["generation_method"] = "downloaded"
                    audit_record["source_file"] = str(matched_photo.relative_to(run_dir))
                else:
                    # No Shopify photo available, skip generation
                    errors.append(f"{token}: No Shopify product photo found, skipping")
                    audit_record["generation_method"] = "skipped"
                    audit_record["error"] = "No Shopify product photo available"
                    audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                    audit_generations.append(audit_record)
                    continue

            # HERO/LIFESTYLE SCENE: Generate with product references
            elif re.match(r"^hero", inner) or "banner_image" in inner or "showcase" in inner:
                # Use brand product refs if available, fall back to bag images (populated from Shopify CDN)
                refs = brand_product_refs or brand_bag_refs
                if not refs:
                    errors.append(f"{token}: No reference images available in brand/assets for {category}, skipping")
                    audit_record["generation_method"] = "skipped"
                    audit_record["error"] = f"No reference images in brand/assets for {category}"
                    audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                    audit_generations.append(audit_record)
                    continue

                description = entry.get("description", "")
                prompt = _hero_prompt(brief, questionnaire, brand_identity, email_num=email_num, total_emails=total_emails, description=description)
                ref_instruction = (
                    f"\n\nREFERENCE IMAGES PROVIDED ({len(refs)} images):\n"
                    "These show the ACTUAL product packaging/bags.\n"
                    "Use these as reference for the product's appearance, colors, and branding.\n"
                    "Compose an original lifestyle scene featuring these products."
                )
                if website_inspo_refs:
                    ref_instruction += (
                        f"\n\nBRAND STYLE REFERENCE ({len(website_inspo_refs)} website screenshots):\n"
                        "These are screenshots of the brand's website. Use them as visual style reference only — "
                        "match the overall aesthetic, color mood, and photographic tone. "
                        "Do NOT reproduce any text, layouts, or UI elements from these screenshots."
                    )
                full_prompt = prompt + ref_instruction
                all_refs = refs + website_inspo_refs

                dest.write_bytes(
                    gemini_image.generate_image_bytes(full_prompt, image_inputs=all_refs, model=model)
                )
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(full_prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(full_prompt)
                audit_record["reference_images"] = [str(p.relative_to(config.root().parent)) for p in all_refs]

            # BENEFITS/BAG IMAGE: Generate with bag and product references
            elif "benefit" in inner.lower() or "bag" in inner.lower():
                refs = brand_bag_refs + brand_product_refs
                if not refs:
                    errors.append(f"{token}: No brand reference images found in brand/assets for {category}, skipping")
                    audit_record["generation_method"] = "skipped"
                    audit_record["error"] = f"No reference images in brand/assets for {category}"
                    audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                    audit_generations.append(audit_record)
                    continue
                
                prompt = "\n".join([
                    f"Create an image for email: {entry.get('description') or inner}",
                    "Style: Clean, professional product photography on neutral background.",
                    f"Show Crispy Beef Bits packaging/product.",
                    "",
                    f"REFERENCE IMAGES PROVIDED ({len(refs)} images):",
                    "These show the ACTUAL product packaging and beef bits appearance.",
                    "Use these as reference for authentic product representation.",
                    "",
                    brand_identity[:2000],
                ])
                
                dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=refs, model=model))
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)
                audit_record["reference_images"] = [str(p.relative_to(config.root().parent)) for p in refs]

            # BENEFIT ICONS: Generate with minimal brand context only
            elif re.match(r"^benefit_[123]_icon$", inner):
                m = re.match(r"^benefit_(\d)_icon$", inner)
                idx = int(m.group(1)) if m else 1
                btok = f"{{{{benefit_{idx}_text}}}}"
                benefit_text = str(copy_tokens.get(btok, ""))
                prompt = _icon_prompt(idx, entry.get("description") or "", benefit_text, brand_identity)
                
                # Icons can be generated without product references (they're abstract)
                dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)
                audit_record["reference_images"] = []

            # USAGE/LIFESTYLE SCENE: tokens like usage_inspiration_image_*, usage_idea_*_image
            elif re.match(r"^usage_", inner) or "inspiration" in inner or "lifestyle" in inner:
                refs = brand_product_refs + website_inspo_refs
                if not refs:
                    errors.append(f"{token}: No brand reference images found, skipping lifestyle scene")
                    audit_record["generation_method"] = "skipped"
                    audit_record["error"] = "No reference images available for lifestyle scene"
                    audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                    audit_generations.append(audit_record)
                    continue

                description = entry.get("description") or "A lifestyle food scene featuring Crispy Beef Bits sprinkled on a dish"
                prompt = "\n".join([
                    "Create a bright, appetizing lifestyle food photograph for an email.",
                    f"Scene: {description}",
                    "Style: Natural daylight, vibrant, premium food photography.",
                    "CRITICAL: Absolutely NO text, NO logos, NO branding, NO watermarks in the image.",
                    "",
                    "BRAND CONTEXT:",
                    brand_identity[:2000],
                ])
                if website_inspo_refs:
                    prompt += (
                        f"\n\nBRAND STYLE REFERENCE ({len(website_inspo_refs)} website screenshots):\n"
                        "Match the overall aesthetic, color mood, and photographic tone of these brand screenshots. "
                        "Do NOT reproduce any text or UI elements."
                    )
                dest.write_bytes(
                    gemini_image.generate_image_bytes(prompt, image_inputs=refs, model=model)
                )
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)
                audit_record["reference_images"] = [str(p.relative_to(config.root().parent)) for p in refs]

            # FALLBACK: Attempt description-based generation using whatever refs are available
            else:
                refs = brand_bag_refs + brand_product_refs
                all_refs = refs + website_inspo_refs
                if not all_refs:
                    errors.append(f"{token}: No generation strategy or reference images available, skipping")
                    audit_record["generation_method"] = "skipped"
                    audit_record["error"] = "No generation strategy and no reference images"
                    audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
                    audit_generations.append(audit_record)
                    continue

                description = entry.get("description") or f"Email image: {inner}"
                prompt = "\n".join([
                    f"Create an email image: {description}",
                    "Style: Clean, professional. No text, no logos, no watermarks.",
                    "",
                    "BRAND CONTEXT:",
                    brand_identity[:2000],
                ])
                dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=all_refs, model=model))
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)
                audit_record["reference_images"] = [str(p.relative_to(config.root().parent)) for p in all_refs]

            images_by_token[token] = rel.replace("\\", "/")
            assets.append({"token": token, "kind": kind, "relative_path": rel.replace("\\", "/")})
            audit_record["output_path"] = rel.replace("\\", "/")
            audit_record["duration_seconds"] = round(time.time() - gen_start, 2)

        except Exception as e:
            msg = f"{token}: {e}"
            errors.append(msg)
            assets.append({"token": token, "kind": "error", "error": str(e)})
            audit_record["error"] = str(e)
            audit_record["duration_seconds"] = round(time.time() - gen_start, 2)
        
        audit_generations.append(audit_record)

    out: Dict[str, Any] = {
        "image_model": model,
        "alts_model": config.text_model(),
        "images_by_token": images_by_token,
        "alts_by_token": alts_by_token,
        "assets": assets,
        "errors": errors,
        "notes": "Image src values are run-relative paths for local preview; set a CDN base in Step 5 or upload files.",
    }

    io_util.write_json(
        run_dir / io_util.step_filename(io_util.STEP4, email_num, total_emails), out
    )
    
    # Write JSON + HTML audit logs
    total_duration = time.time() - start_time
    _write_image_audit_log(
        run_dir=run_dir,
        image_generations=audit_generations,
        total_duration_seconds=total_duration,
        model=model,
        email_num=email_num,
        total_emails=total_emails,
        alt_text_generation=None,
    )
    
    return out
