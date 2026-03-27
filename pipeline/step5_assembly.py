"""Step 5: HTML assembly — merge all outputs, upload images to Klaviyo, emit final HTML."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import config, effective, io_util, klaviyo_client, questionnaire as questionnaire_module


def _build_static_tokens(questionnaire: Dict[str, Any]) -> Dict[str, str]:
    year = datetime.now(timezone.utc).year
    return {
        "{{current_year}}": str(year),
        "{{brand_name}}": "Yay's Beef Crisps",
        "{{company_name}}": "Yay's Beef Crisps",
        "{{company_address}}": questionnaire.get("company_address", "123 Snack Street, Flavor Town, CA 90210"),
        "{{unsubscribe_link}}": "{% unsubscribe %}",
        "{{preferences_link}}": "{% manage_preferences %}",
        "{{legal_text}}": "No longer want to receive these emails? You can unsubscribe or manage your preferences.",
        "{{header_logo_alt}}": "Yay's Beef Crisps",
    }


def _build_social_tokens() -> Dict[str, str]:
    """Static social/footer tokens — all values sourced from env vars via config."""
    _LOGO = config.brand_logo_url()
    _IG_ICON = "https://cdn.klaviyo.com/icons/instagram.png"
    _TT_ICON = "https://cdn.klaviyo.com/icons/tiktok.png"
    _FB_ICON = "https://cdn.klaviyo.com/icons/facebook.png"
    return {
        # Canonical names
        "{{instagram_icon_image}}": _IG_ICON,
        "{{tiktok_icon_image}}": _TT_ICON,
        "{{facebook_icon_image}}": _FB_ICON,
        "{{footer_instagram_link}}": config.brand_instagram_url(),
        "{{footer_tiktok_link}}": config.brand_tiktok_url(),
        "{{footer_facebook_link}}": config.brand_facebook_url(),
        "{{footer_logo_image}}": _LOGO,
        "{{footer_signoff}}": "The Yay's Team",
        "{{footer_social}}": "",
        # Aliases for LLM-invented variant names
        "{{footer_logo}}": _LOGO,
        "{{header_logo_url}}": _LOGO,
        "{{social_icon_instagram}}": _IG_ICON,
        "{{social_icon_tiktok}}": _TT_ICON,
        "{{social_icon_facebook}}": _FB_ICON,
        "{{instagram_icon}}": _IG_ICON,
        "{{tiktok_icon}}": _TT_ICON,
        "{{facebook_icon}}": _FB_ICON,
    }


def _upload_generated_images(
    run_dir: Path,
    images_data: Dict[str, Any],
    skip_upload: bool = False,
    email_num: int = 1,
    total_emails: int = 1,
) -> Dict[str, str]:
    """
    Upload local generated images to Klaviyo CDN.
    Returns token -> hosted_url mapping.

    If skip_upload=True, returns file:// URLs for local preview.
    """
    images_by_token = images_data.get("images_by_token") or {}
    assets = images_data.get("assets") or []

    token_to_url: Dict[str, str] = {}

    for token, rel_path in images_by_token.items():
        local = run_dir / rel_path
        if not local.is_file():
            continue

        # Check if this was downloaded from Shopify (don't re-upload)
        asset_meta = next((a for a in assets if a.get("token") == token), {})
        if asset_meta.get("kind") == "downloaded":
            # Already a public URL from Shopify; match by product index from token name
            products_data = io_util.read_json(
                run_dir / io_util.step_filename(io_util.STEP2C, email_num, total_emails)
            )
            featured = products_data.get("featured_products") or []
            url = None
            # Try numeric index match: product_1_image -> featured[0], etc.
            m = re.match(r"product_(\d+)_image", token.strip("{}"))
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(featured):
                    url = featured[idx].get("primary_image_url", "")
            # Fallback: match by handle in local filename
            if not url:
                for p in featured:
                    handle = p.get("handle", "")
                    if handle and handle in local.name:
                        url = p.get("primary_image_url", "")
                        break
            if url:
                token_to_url[token] = url
            else:
                token_to_url[token] = f"file://{local.resolve()}"
            continue
        
        if skip_upload:
            token_to_url[token] = f"file://{local.resolve()}"
        else:
            try:
                result = klaviyo_client.upload_image(local, name=local.stem)
                token_to_url[token] = result["image_url"]
            except Exception as e:
                raise RuntimeError(f"Failed to upload {token} ({local.name}): {e}")
    
    return token_to_url


def _assemble_html(
    skeleton: str,
    copy_tokens: Dict[str, str],
    link_tokens: Dict[str, str],
    image_tokens: Dict[str, str],
    alt_tokens: Dict[str, str],
    static_tokens: Dict[str, str],
    social_tokens: Dict[str, str],
) -> str:
    """Replace all {{tokens}} in the skeleton."""
    html = skeleton
    
    # Normalize all token keys to include {{ }} brackets
    def normalize_token(key: str) -> str:
        if not key.startswith("{{"):
            return f"{{{{{key}}}}}"
        return key
    
    all_subs = {}
    # Apply in priority order: link/image/static first, copy last (copy takes precedence)
    for k, v in link_tokens.items():
        all_subs[normalize_token(k)] = v
    all_subs.update({normalize_token(k): v for k, v in image_tokens.items()})
    all_subs.update({normalize_token(k): v for k, v in alt_tokens.items()})
    all_subs.update({normalize_token(k): v for k, v in static_tokens.items()})
    all_subs.update({normalize_token(k): v for k, v in social_tokens.items()})
    # Copy tokens applied last — highest priority (overrides any misclassified link tokens)
    for k, v in copy_tokens.items():
        all_subs[normalize_token(k)] = v
    
    for token, value in all_subs.items():
        if value is None:
            continue
        html = html.replace(token, value)
    
    return html


def _find_missing_tokens(html: str) -> List[str]:
    """Find any remaining {{tokens}} that weren't substituted."""
    return re.findall(r"\{\{[^}]+\}\}", html)


def run(
    run_dir: Path,
    skip_upload: bool = False,
    email_num: int = 1,
    total_emails: int = 1,
) -> Dict[str, Any]:
    """
    Assemble final HTML email.

    Args:
        run_dir: output/<run_id>/
        skip_upload: if True, skip Klaviyo uploads and use file:// URLs for preview
        email_num: 1-based index of the email in a sequence (1 = single email)
        total_emails: total number of emails in the sequence (1 = single email)

    Returns:
        {
            "email_final_path": "output/<run>/email_final.html",  (or email_N_final.html)
            "email_preview_path": "output/<run>/email_preview.html",
            "uploaded_images": [{token, klaviyo_url, image_id}, ...],
            "missing_tokens": ["{{token}}", ...],
        }
    """
    structure = effective.effective_structure(run_dir, email_num, total_emails)
    copy = effective.effective_copy(run_dir, email_num, total_emails)
    links_data = effective.effective_links(run_dir, email_num, total_emails)
    images_data = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP4, email_num, total_emails)
    )
    discount_data = io_util.read_json(run_dir / io_util.STEP2B)
    products_data = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2C, email_num, total_emails)
    )
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    skeleton = structure.get("html_skeleton", "")
    if not skeleton:
        raise ValueError("No html_skeleton in structure data")

    # Build token maps
    copy_tokens = copy.get("copy_by_token") or {}
    link_tokens = links_data.get("links_by_token") or {}
    alt_tokens = images_data.get("alts_by_token") or {}
    static_tokens = _build_static_tokens(questionnaire)
    social_tokens = _build_social_tokens()

    # Safety net: ensure subject/preheader tokens are always resolvable — step2d may have
    # generated them as top-level fields but not copied them into copy_by_token
    if "{{email_subject}}" not in copy_tokens and copy.get("subject_line"):
        copy_tokens["{{email_subject}}"] = copy["subject_line"]
    if "{{preheader_text}}" not in copy_tokens and copy.get("preheader"):
        copy_tokens["{{preheader_text}}"] = copy["preheader"]

    # Enforce brand social URLs from config — overrides anything step3 may have set to None
    _SOCIAL_CONFIG = {
        "{{instagram_link}}": config.brand_instagram_url(),
        "{{tiktok_link}}": config.brand_tiktok_url(),
        "{{facebook_link}}": config.brand_facebook_url(),
    }
    for token, url in _SOCIAL_CONFIG.items():
        if url:
            link_tokens[token] = url

    # Inject discount code directly (source_agent="discount" tokens)
    discount_code = discount_data.get("discount_code") or ""
    if discount_code:
        static_tokens["{{discount_code}}"] = discount_code

    # Inject product prices from step 2C (not from links/copy — authoritative source)
    featured = products_data.get("featured_products") or []
    for i, product in enumerate(featured, 1):
        price = product.get("price", "")
        if price:
            copy_tokens[f"{{{{product_{i}_price}}}}"] = f"${price}" if not str(price).startswith("$") else str(price)
    
    # Upload generated images to Klaviyo (or use local paths if skip_upload)
    image_tokens = _upload_generated_images(
        run_dir, images_data, skip_upload=skip_upload,
        email_num=email_num, total_emails=total_emails,
    )

    # Assemble final HTML
    final_html = _assemble_html(
        skeleton,
        copy_tokens,
        link_tokens,
        image_tokens,
        alt_tokens,
        static_tokens,
        social_tokens,
    )

    # Check for missing tokens
    missing = _find_missing_tokens(final_html)

    # Determine output filenames (numbered for sequences)
    if total_emails > 1:
        final_path = run_dir / f"email_{email_num}_final.html"
        preview_path = run_dir / f"email_{email_num}_preview.html"
    else:
        final_path = run_dir / "email_final.html"
        preview_path = run_dir / "email_preview.html"

    # Write final HTML (Klaviyo-ready with CDN URLs)
    final_path.write_text(final_html, encoding="utf-8")

    # Write preview HTML (always with local file:// paths)
    preview_tokens = _upload_generated_images(
        run_dir, images_data, skip_upload=True,
        email_num=email_num, total_emails=total_emails,
    )
    preview_html = _assemble_html(
        skeleton,
        copy_tokens,
        link_tokens,
        preview_tokens,
        alt_tokens,
        static_tokens,
        social_tokens,
    )
    preview_path.write_text(preview_html, encoding="utf-8")
    
    # Collect upload metadata
    uploaded: List[Dict[str, str]] = []
    if not skip_upload:
        for token, url in image_tokens.items():
            if url.startswith("http"):
                uploaded.append({"token": token, "url": url})
    
    out = {
        "email_final_path": str(final_path),
        "email_preview_path": str(preview_path),
        "uploaded_images": uploaded,
        "missing_tokens": missing,
        "skip_upload": skip_upload,
    }
    
    io_util.write_json(
        run_dir / io_util.step_filename(io_util.STEP5, email_num, total_emails), out
    )
    return out
