# PRD 01 — Project Scaffolding, Config, IO, and Shared Brand Migration

## Objective

Set up the `email_gen/` directory structure, configuration system, I/O utilities, and migrate brand files to a shared top-level `brand/` directory that both `ads_gen_v2` and `email_gen` reference.

---

## 1. Shared Brand File Migration

### Current State

Brand identity text lives in `ads_gen_v2/brand_identity_text/`:
```
ads_gen_v2/brand_identity_text/
├── key_brand_attributes.txt          # 57 lines of global brand identity
├── README.txt
└── product_categories/
    ├── beef_crisps/
    │   ├── positioning.txt           # 24 lines
    │   └── README.txt
    ├── pork_crisps/
    │   └── ...
    └── crispy_beef_bits/
        └── ...
```

Brand assets live in `ads_gen_v2/brand_assets/`:
```
ads_gen_v2/brand_assets/
├── brand_logo/
├── product_images/<category>/<flavor>/
├── bag_images/<category>/<flavor>/
└── flavor_identity/<category>/<flavor>/*.txt
```

### Target State

Move to repo root `brand/`:
```
static_ads_gen/brand/
├── identity_text/
│   ├── key_brand_attributes.txt
│   ├── README.txt
│   └── product_categories/
│       ├── beef_crisps/positioning.txt
│       ├── pork_crisps/...
│       └── crispy_beef_bits/...
└── assets/
    ├── brand_logo/
    ├── product_images/<category>/<flavor>/
    ├── bag_images/<category>/<flavor>/
    └── flavor_identity/<category>/<flavor>/*.txt
```

### Migration Steps

1. `mkdir -p brand/identity_text brand/assets`
2. `mv ads_gen_v2/brand_identity_text/* brand/identity_text/`
3. `mv ads_gen_v2/brand_assets/* brand/assets/`
4. Create symlinks for backward compatibility:
   - `ads_gen_v2/brand_identity_text` → `../brand/identity_text`
   - `ads_gen_v2/brand_assets` → `../brand/assets`
5. Verify `ads_gen_v2` still works by running `python main.py list-products` from `ads_gen_v2/`.

### ads_gen_v2 Config Update

In `ads_gen_v2/pipeline/config.py`, the functions `brand_identity_dir()` and `brand_assets_dir()` currently return paths relative to `_ROOT` (which is `ads_gen_v2/`). After migration, the symlinks will make these paths still resolve correctly. No code change needed if symlinks are used. If we prefer explicit paths:

```python
def brand_assets_dir() -> Path:
    shared = _ROOT.parent / "brand" / "assets"
    if shared.is_dir():
        return shared
    return _ROOT / "brand_assets"  # fallback

def brand_identity_dir() -> Path:
    shared = _ROOT.parent / "brand" / "identity_text"
    if shared.is_dir():
        return shared
    return _ROOT / "brand_identity_text"  # fallback
```

---

## 2. email_gen/pipeline/config.py

Mirrors the pattern from `ads_gen_v2/pipeline/config.py` (see `ads_gen_v2/pipeline/config.py` lines 1-126 for reference).

```python
"""Paths and environment-driven model settings for email_gen."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Set, Tuple

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
    return _ROOT.parent / "ads_gen_v2" / "brand_identity_text"  # fallback


def brand_assets_dir() -> Path:
    shared = _ROOT.parent / "brand" / "assets"
    if shared.is_dir():
        return shared
    return _ROOT.parent / "ads_gen_v2" / "brand_assets"  # fallback


def brand_identity_product_categories_dir() -> Path:
    return brand_identity_dir() / "product_categories"


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


# ── Per-agent model config ─────────────────────────────────────────────

def brief_model() -> str:
    return os.getenv("EMAIL_BRIEF_MODEL", "gemini-2.5-pro").strip()

def structure_model() -> str:
    return os.getenv("EMAIL_STRUCTURE_MODEL", "gemini-2.5-flash").strip()

def discount_model() -> str:
    return os.getenv("EMAIL_DISCOUNT_MODEL", "gemini-2.5-flash").strip()

def products_model() -> str:
    return os.getenv("EMAIL_PRODUCTS_MODEL", "gemini-2.5-flash").strip()

def copy_model() -> str:
    return os.getenv("EMAIL_COPY_MODEL", "gemini-2.5-pro").strip()

def links_model() -> str:
    return os.getenv("EMAIL_LINKS_MODEL", "gemini-2.5-flash").strip()

def cohesion_model() -> str:
    return os.getenv("EMAIL_COHESION_MODEL", "gemini-2.5-pro").strip()

def image_model() -> str:
    return os.getenv("EMAIL_IMAGE_MODEL", "gemini-3-pro-image-preview").strip()

def assembly_model() -> str:
    return os.getenv("EMAIL_ASSEMBLY_MODEL", "gemini-2.5-pro").strip()
```

---

## 3. email_gen/pipeline/io_util.py

Direct adaptation of `ads_gen_v2/pipeline/io_util.py` (lines 1-128). Key differences: more artifact filenames for the email pipeline steps.

```python
"""Run folders and JSON artifacts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import config

# Artifact filenames
STEP1 = "step1_brief.json"
STEP2A = "step2a_structure.json"
STEP2B = "step2b_discount.json"
STEP2C = "step2c_products.json"
STEP2D = "step2d_copy.json"
STEP2E = "step2e_links.json"
STEP3 = "step3_cohesion.json"
STEP4 = "step4_images.json"
STEP5 = "step5_assembly.json"


def ensure_output() -> Path:
    p = config.output_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_run_id(name: Optional[str] = None) -> str:
    if name:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_") or "run"
        return safe
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")


def run_dir(run_id: str) -> Path:
    return ensure_output() / run_id


def init_run(run_id: str, questionnaire_path: Optional[Path] = None) -> Path:
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "images").mkdir(exist_ok=True)
    meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    if questionnaire_path and questionnaire_path.is_file():
        dest = d / "questionnaire.yaml"
        shutil.copy2(questionnaire_path, dest)
        meta["questionnaire"] = str(dest)
    write_json(d / "meta.json", meta)
    return d


def load_meta(run_dir: Path) -> Dict[str, Any]:
    p = run_dir / "meta.json"
    if not p.is_file():
        return {}
    return read_json(p)


def patch_meta(run_dir: Path, **updates: Any) -> Dict[str, Any]:
    meta = load_meta(run_dir)
    for k, v in updates.items():
        if v is not None:
            meta[k] = v
    write_json(run_dir / "meta.json", meta)
    return meta


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_step(run_id: str, filename: str) -> Optional[Dict[str, Any]]:
    p = run_dir(run_id) / filename
    if p.exists():
        return read_json(p)
    return None
```

---

## 4. email_gen/pipeline/gemini_text.py

Copy the pattern from `ads_gen_v2/pipeline/gemini_text.py` (lines 1-141). The key functions are:

- `_client()` — creates `genai.Client` with API key
- `generate_text(prompt, model, system)` — single-turn text generation
- `generate_text_with_images(prompt, images, model, system)` — multimodal generation
- `load_brand_identity_text(product_category, flavor)` — hierarchical brand text loading

The only difference: `config.brand_identity_dir()` and related paths point to the shared `brand/` location via our new `config.py`.

The `load_brand_identity_text` function must work identically:
1. Load `brand/identity_text/*.txt` (skip README.txt) as `[GLOBAL BRAND]`
2. Load `brand/identity_text/product_categories/<category>/*.txt` as `[PRODUCT LINE: <category>]`
3. Load `brand/assets/flavor_identity/<category>/<flavor>/*.txt` as `[SKU FLAVOR: <category>/<flavor>]`
4. Join with `\n\n---\n\n` separators

---

## 5. email_gen/pipeline/gemini_image.py

Copy the pattern from `ads_gen_v2/pipeline/gemini_image.py` (lines 1-77). The key function is:

- `generate_image_bytes(prompt, image_inputs, model)` — text + optional reference images → PNG bytes

Uses `GenerateContentConfig(response_modalities=[Modality.TEXT, Modality.IMAGE])` with the `google-genai` SDK. Extracts image bytes from `inline_data.data` or `as_image()` on response parts.

---

## 6. email_gen/.env.example

```
# Copy to .env in this folder (email_gen/.env)

# Per-agent model overrides (defaults shown)
# EMAIL_BRIEF_MODEL=gemini-2.5-pro
# EMAIL_STRUCTURE_MODEL=gemini-2.5-flash
# EMAIL_DISCOUNT_MODEL=gemini-2.5-flash
# EMAIL_PRODUCTS_MODEL=gemini-2.5-flash
# EMAIL_COPY_MODEL=gemini-2.5-pro
# EMAIL_LINKS_MODEL=gemini-2.5-flash
# EMAIL_COHESION_MODEL=gemini-2.5-pro
# EMAIL_IMAGE_MODEL=gemini-3-pro-image-preview
# EMAIL_ASSEMBLY_MODEL=gemini-2.5-pro

# Shared credentials are in the repo root .env:
# GOOGLE_API_KEY=...
# SHOPIFY_SHOP_URL=...
# SHOPIFY_ADMIN_API_TOKEN=...
```

---

## 7. email_gen/requirements.txt

```
google-genai>=1.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
requests>=2.31.0
PyYAML>=6.0
```

---

## 8. Test Checkpoint

After implementing this phase:

1. `cd email_gen && python -c "from pipeline import config; print(config.brand_identity_dir())"` should print the shared brand path
2. `python -c "from pipeline import config; print(config.google_api_key())"` should print the API key from root `.env`
3. `python -c "from pipeline import gemini_text; print(gemini_text.load_brand_identity_text()[:200])"` should print the first 200 chars of brand identity
4. `python main.py init-run --name test_run` should create `output/test_run/meta.json`
5. From `ads_gen_v2/`: `python main.py list-products` should still work (brand migration didn't break anything)
