"""Step 4: Image generation — raster assets + alt text for image-agent tokens."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from . import config, effective, gemini_image, gemini_text, io_util, questionnaire as questionnaire_module

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


def run(run_dir: Path) -> Dict[str, Any]:
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


def _find_brand_product_images(category: str, flavor: Optional[str] = None) -> List[Path]:
    """
    Find product reference images from brand/assets/product_images.
    Returns lifestyle shots showing the product in use.
    
    Args:
        category: e.g., "crispy_beef_bits", "beef_crisps"
        flavor: e.g., "original", "spicy", "teriyaki" (optional)
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


def _find_brand_bag_images(category: str, flavor: Optional[str] = None) -> List[Path]:
    """
    Find bag/packaging images from brand/assets/bag_images.
    Returns product packaging shots.
    
    Args:
        category: e.g., "crispy_beef_bits", "beef_crisps"
        flavor: e.g., "original", "spicy", "teriyaki" (optional)
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

    raw = gemini_text.generate_text(
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


def _hero_prompt(brief: Dict[str, Any], questionnaire: Dict[str, Any], identity: str) -> str:
    return "\n".join(
        [
            "Create a wide hero photograph for an email header (landscape, ~3:1 or 2:1).",
            "Subject: appetizing summer meal scene — bowl or plate with salad, noodles, or rice; Crispy Beef Bits visible as a crunchy topping.",
            "Natural daylight, vibrant but tasteful, premium food photography.",
            "",
            "CRITICAL: Absolutely NO text, NO logos, NO branding, NO watermarks, NO product packaging with visible labels in the image.",
            "The brand logo will be added separately as an overlay in the email template.",
            "Generate ONLY the lifestyle food photography scene without any text or branding elements.",
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
    )


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


def _logo_prompt(identity: str) -> str:
    return "\n".join(
        [
            "Create a clean horizontal brand logo on a transparent or solid white background.",
            "Snack brand: Yay's Beef Crisps — artisanal beef crisps, Cambodian heritage.",
            "Legible wordmark; appetizing but not cluttered. Suitable for ~150px width in email header.",
            "No URLs, no extra trademark symbols beyond normal ® if subtle.",
            "",
            identity[:3000],
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


def _write_image_audit_log(
    run_dir: Path,
    image_generations: List[Dict[str, Any]],
    total_duration_seconds: float,
    model: str,
    alt_text_generation: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write detailed audit log for image generation step.
    
    Args:
        run_dir: output/<run_id>/
        image_generations: List of per-image generation records
        total_duration_seconds: Total time for entire step
        model: Image model used
        alt_text_generation: Optional record of alt text generation (if performed)
    """
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(exist_ok=True)
    
    audit_record = {
        "step_id": "step4_images",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "image_model": model,
        "total_duration_seconds": round(total_duration_seconds, 2),
        "total_images_generated": len([g for g in image_generations if g["generation_method"] == "generated"]),
        "total_images_downloaded": len([g for g in image_generations if g["generation_method"] == "downloaded"]),
        "total_images_copied": len([g for g in image_generations if g["generation_method"] == "copied"]),
        "image_generations": image_generations,
        "alt_text_generation": alt_text_generation,
    }
    
    audit_path = audit_dir / "step4_images.audit.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_record, f, indent=2, ensure_ascii=False)


def run(run_dir: Path) -> Dict[str, Any]:
    start_time = time.time()
    
    brief = io_util.read_json(run_dir / io_util.STEP1)
    structure = effective.effective_structure(run_dir)
    products_data = io_util.read_json(run_dir / io_util.STEP2C)
    copy = effective.effective_copy(run_dir)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    focus = questionnaire.get("product_focus", "")
    pc = focus if focus not in ("all", "") else None
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)

    manifest = structure.get("token_manifest") or []
    image_slots = [t for t in manifest if t.get("source_agent") == "image" and not _is_alt_token(t.get("token", ""))]

    images_dir = run_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    alts_by_token = _generate_alts(manifest, brief, copy, brand_identity)

    images_by_token: Dict[str, str] = {}
    assets: List[Dict[str, Any]] = []
    errors: List[str] = []
    audit_generations: List[Dict[str, Any]] = []

    featured = products_data.get("featured_products") or []
    copy_tokens = copy.get("copy_by_token") or {}

    model = config.image_model()

    # Reference image for hero (sampler pack photo when available)
    sampler = _match_featured_by_slug(featured, "sampler")
    hero_refs: List[Path] = []
    ref_path: Optional[Path] = None
    if sampler and sampler.get("primary_image_url"):
        ref_path = images_dir / "_ref_sampler_for_hero.jpg"
        try:
            _download_url(str(sampler["primary_image_url"]), ref_path)
            hero_refs.append(ref_path)
        except Exception as e:
            errors.append(f"hero_ref_download: {e}")
            ref_path = None

    for entry in image_slots:
        token = entry["token"]
        inner = _token_inner(token)
        safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", inner).strip("_") or "image"
        rel = f"images/{safe_name}.png"
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
            if inner in ("brand_logo_image", "header_logo_image", "header_logo"):
                logo = _first_brand_logo_file()
                if logo:
                    ext = logo.suffix.lower() or ".png"
                    rel = f"images/{safe_name}{ext}"
                    dest = run_dir / rel
                    shutil.copy2(logo, dest)
                    kind = "copied"
                    audit_record["generation_method"] = "copied"
                    audit_record["source_file"] = str(logo)
                else:
                    prompt = _logo_prompt(brand_identity)
                    dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                    kind = "generated"
                    audit_record["generation_method"] = "generated"
                    audit_record["prompt"] = _truncate(prompt, 8000)
                    audit_record["prompt_hash"] = _hash_text(prompt)

            elif inner == "hero_image":
                prompt = _hero_prompt(brief, questionnaire, brand_identity)
                inputs = hero_refs if hero_refs else None
                extra = (
                    "\n\nUse the provided product photo as reference for how the Crispy Beef Bits "
                    "packaging/product looks; compose an original lifestyle scene — do not paste the pack as-is only."
                    if inputs
                    else ""
                )
                full_prompt = prompt + extra
                dest.write_bytes(
                    gemini_image.generate_image_bytes(full_prompt, image_inputs=inputs, model=model)
                )
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(full_prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(full_prompt)
                if inputs:
                    audit_record["reference_images"] = [str(p.relative_to(run_dir)) for p in inputs]

            elif inner.startswith("product_spotlight_") and inner.endswith("_image"):
                slug = _spotlight_slug(inner) or "sampler"
                prod = _match_featured_by_slug(featured, slug)
                if prod and prod.get("primary_image_url"):
                    ext = _extension_from_url_or_ct(str(prod["primary_image_url"]), None)
                    rel = f"images/{safe_name}{ext}"
                    dest = run_dir / rel
                    _download_url(str(prod["primary_image_url"]), dest)
                    kind = "downloaded"
                    audit_record["generation_method"] = "downloaded"
                    audit_record["source_url"] = str(prod["primary_image_url"])
                else:
                    prompt = "\n".join(
                        [
                            "Professional product pack shot on neutral background, e-commerce style.",
                            entry.get("description") or "Featured product",
                            brand_identity[:2000],
                        ]
                    )
                    dest = run_dir / f"images/{safe_name}.png"
                    rel = str(dest.relative_to(run_dir))
                    dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                    kind = "generated"
                    audit_record["generation_method"] = "generated"
                    audit_record["prompt"] = _truncate(prompt, 8000)
                    audit_record["prompt_hash"] = _hash_text(prompt)

            elif re.match(r"^benefit_[123]_icon$", inner):
                m = re.match(r"^benefit_(\d)_icon$", inner)
                idx = int(m.group(1)) if m else 1
                btok = f"{{{{benefit_{idx}_text}}}}"
                benefit_text = str(copy_tokens.get(btok, ""))
                prompt = _icon_prompt(idx, entry.get("description") or "", benefit_text, brand_identity)
                dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)

            elif re.match(r"^product_\d+_image$", inner):
                # Extract product index (e.g., "product_1_image" -> 1)
                m = re.match(r"^product_(\d+)_image$", inner)
                prod_idx = int(m.group(1)) if m else 1
                # Get the corresponding product from featured_products list (1-indexed)
                if 0 < prod_idx <= len(featured):
                    prod = featured[prod_idx - 1]
                    if prod.get("primary_image_url"):
                        ext = _extension_from_url_or_ct(str(prod["primary_image_url"]), None)
                        rel = f"images/{safe_name}{ext}"
                        dest = run_dir / rel
                        _download_url(str(prod["primary_image_url"]), dest)
                        kind = "downloaded"
                        audit_record["generation_method"] = "downloaded"
                        audit_record["source_url"] = str(prod["primary_image_url"])
                    else:
                        # Fallback to generation if no Shopify image
                        prompt = "\n".join(
                            [
                                "Professional product pack shot on neutral background, e-commerce style.",
                                entry.get("description") or inner,
                                brand_identity[:2000],
                            ]
                        )
                        dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                        kind = "generated"
                        audit_record["generation_method"] = "generated"
                        audit_record["prompt"] = _truncate(prompt, 8000)
                        audit_record["prompt_hash"] = _hash_text(prompt)
                else:
                    # Product index out of range, generate
                    prompt = "\n".join(
                        [
                            "Professional product pack shot on neutral background, e-commerce style.",
                            entry.get("description") or inner,
                            brand_identity[:2000],
                        ]
                    )
                    dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                    kind = "generated"
                    audit_record["generation_method"] = "generated"
                    audit_record["prompt"] = _truncate(prompt, 8000)
                    audit_record["prompt_hash"] = _hash_text(prompt)

            else:
                prompt = "\n".join(
                    [
                        "Email marketing image asset.",
                        entry.get("description") or inner,
                        brand_identity[:2500],
                    ]
                )
                dest.write_bytes(gemini_image.generate_image_bytes(prompt, image_inputs=None, model=model))
                kind = "generated"
                audit_record["generation_method"] = "generated"
                audit_record["prompt"] = _truncate(prompt, 8000)
                audit_record["prompt_hash"] = _hash_text(prompt)

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

    # Drop temp ref from published paths (still on disk for debugging)
    if ref_path and ref_path.is_file():
        assets.append(
            {
                "token": "_internal",
                "kind": "reference_only",
                "relative_path": str(ref_path.relative_to(run_dir)).replace("\\", "/"),
            }
        )

    out: Dict[str, Any] = {
        "image_model": model,
        "alts_model": config.text_model(),
        "images_by_token": images_by_token,
        "alts_by_token": alts_by_token,
        "assets": assets,
        "errors": errors,
        "notes": "Image src values are run-relative paths for local preview; set a CDN base in Step 5 or upload files.",
    }

    io_util.write_json(run_dir / io_util.STEP4, out)
    
    # Write detailed audit log
    total_duration = time.time() - start_time
    _write_image_audit_log(
        run_dir=run_dir,
        image_generations=audit_generations,
        total_duration_seconds=total_duration,
        model=model,
        alt_text_generation=None,  # Could add alt text generation details here if needed
    )
    
    return out
