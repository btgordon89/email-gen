"""Paths and environment-driven model settings for email_gen."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent  # email_gen/
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT.parent / ".env")  # repo root .env


def root() -> Path:
    return _ROOT


# ── Brand paths (shared) ──────────────────────────────────────────────


def brand_identity_dir() -> Path:
    shared = _ROOT.parent / "brand" / "identity_text"
    if shared.is_dir():
        return shared
    return _ROOT.parent / "ads_gen" / "brand_identity_text"


def brand_assets_dir() -> Path:
    shared = _ROOT.parent / "brand" / "assets"
    if shared.is_dir():
        return shared
    return _ROOT.parent / "ads_gen" / "brand_assets"


def brand_identity_product_categories_dir() -> Path:
    return brand_identity_dir() / "product_categories"


def review_highlights_path() -> Path:
    return _ROOT.parent / "brand" / "customer_reviews" / "review_highlights.txt"


def brand_website_inspo_dir() -> Path:
    return _ROOT.parent / "brand" / "website"


def brand_logo_dir() -> Path:
    return brand_assets_dir() / "brand_logo"


def product_images_dir(category: str, flavor: str) -> Path:
    return brand_assets_dir() / "product_images" / category / flavor


def bag_images_dir(category: str, flavor: str) -> Path:
    return brand_assets_dir() / "bag_images" / category / flavor


def flavor_identity_dir(category: str, flavor: str) -> Path:
    return brand_assets_dir() / "flavor_identity" / category / flavor


# ── Output ─────────────────────────────────────────────────────────────


def output_dir() -> Path:
    return _ROOT / "output"


def email_templates_dir() -> Path:
    return _ROOT / "email_templates"


# ── API keys ───────────────────────────────────────────────────────────


def google_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        raise ValueError("Set GOOGLE_API_KEY in .env")
    return key


def shopify_shop_url() -> str:
    url = os.getenv("SHOPIFY_SHOP_URL", "").strip()
    if not url:
        raise ValueError("Set SHOPIFY_SHOP_URL in .env")
    return url


def shopify_admin_api_token() -> str:
    token = os.getenv("SHOPIFY_ADMIN_API_TOKEN", "").strip()
    if not token:
        raise ValueError("Set SHOPIFY_ADMIN_API_TOKEN in .env")
    return token


def klaviyo_api_key() -> str:
    key = os.getenv("KLAVIYO_API_KEY", "").strip()
    if not key:
        raise ValueError("Set KLAVIYO_API_KEY in .env")
    return key


def brand_storefront_url() -> str:
    """Brand public storefront URL. Set BRAND_STOREFRONT_URL in .env."""
    return os.getenv("BRAND_STOREFRONT_URL", "").strip()


def brand_logo_url() -> str:
    """Brand logo image URL (hosted). Set BRAND_LOGO_URL in .env."""
    return os.getenv("BRAND_LOGO_URL", "").strip()


def brand_instagram_url() -> str:
    """Brand Instagram profile URL. Set BRAND_INSTAGRAM_URL in .env."""
    return os.getenv("BRAND_INSTAGRAM_URL", "").strip()


def brand_tiktok_url() -> str:
    """Brand TikTok profile URL. Set BRAND_TIKTOK_URL in .env."""
    return os.getenv("BRAND_TIKTOK_URL", "").strip()


def brand_facebook_url() -> str:
    """Brand Facebook page URL. Set BRAND_FACEBOOK_URL in .env."""
    return os.getenv("BRAND_FACEBOOK_URL", "").strip()


# ── Per-agent model config ─────────────────────────────────────────────

# Env var names for each step (used for override lookup)
_STEP_ENV_VARS: Dict[str, str] = {
    "step1_brief": "EMAIL_BRIEF_MODEL",
    "step2a_structure": "EMAIL_STRUCTURE_MODEL",
    "step2b_discount": "EMAIL_DISCOUNT_MODEL",
    "step2c_products": "EMAIL_PRODUCTS_MODEL",
    "step2d_copy": "EMAIL_COPY_MODEL",
    "step2e_links": "EMAIL_LINKS_MODEL",
    "step3_cohesion": "EMAIL_COHESION_MODEL",
    "step4_images": "EMAIL_IMAGE_MODEL",
    "step5_assembly": "EMAIL_ASSEMBLY_MODEL",
    "step7_review": "EMAIL_REVIEW_MODEL",
    "step7b_patch": "EMAIL_PATCH_MODEL",
}

_STEP_DEFAULTS: Dict[str, str] = {
    "step1_brief": "gemini-2.5-pro",
    "step2a_structure": "gemini-2.5-flash",
    "step2b_discount": "gemini-2.5-flash",
    "step2c_products": "gemini-2.5-flash",
    "step2d_copy": "gemini-2.5-pro",
    "step2e_links": "gemini-2.5-flash",
    "step3_cohesion": "gemini-2.5-pro",
    "step4_images": "gemini-3-pro-image-preview",
    "step5_assembly": "gemini-2.5-pro",
    "step7_review": "gemini-2.5-pro",
    "step7b_patch": "gemini-2.5-pro",
}


@lru_cache(maxsize=1)
def _load_models_yaml() -> Dict[str, str]:
    """Load step→model mapping from models_config.yaml. Cached after first load."""
    yaml_path = _ROOT / "pipeline" / "models_config.yaml"
    if not yaml_path.is_file():
        return {}
    with yaml_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("steps", {})


def _model_for_step(step_id: str) -> str:
    """
    Resolve model for a step using priority: env var > models_config.yaml > default.
    """
    env_var = _STEP_ENV_VARS.get(step_id)
    if env_var:
        env_val = os.getenv(env_var, "").strip()
        if env_val:
            return env_val

    yaml_steps = _load_models_yaml()
    if step_id in yaml_steps and yaml_steps[step_id]:
        return str(yaml_steps[step_id]).strip()

    return _STEP_DEFAULTS.get(step_id, "gemini-2.5-flash")


def reload_models_config() -> None:
    """Force reload of models_config.yaml (clears cache). Useful in tests."""
    _load_models_yaml.cache_clear()


def text_model() -> str:
    """Default text model for generic Gemini helpers."""
    return os.getenv("EMAIL_TEXT_MODEL", "gemini-2.5-flash").strip()


def brief_model() -> str:
    return _model_for_step("step1_brief")


def structure_model() -> str:
    return _model_for_step("step2a_structure")


def discount_model() -> str:
    return _model_for_step("step2b_discount")


def products_model() -> str:
    return _model_for_step("step2c_products")


def copy_model() -> str:
    return _model_for_step("step2d_copy")


def links_model() -> str:
    return _model_for_step("step2e_links")


def cohesion_model() -> str:
    return _model_for_step("step3_cohesion")


def image_model() -> str:
    return _model_for_step("step4_images")


def assembly_model() -> str:
    return _model_for_step("step5_assembly")


def review_model() -> str:
    return _model_for_step("step7_review")


def patch_model() -> str:
    return _model_for_step("step7b_patch")
