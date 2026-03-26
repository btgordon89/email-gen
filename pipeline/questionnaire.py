"""Load, validate, and summarize campaign questionnaire YAML."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

import yaml

from . import config

PRIMARY_GOALS = frozenset(
    {
        "drive_sales",
        "clear_inventory",
        "introduce_new_product",
        "re_engage",
        "announce_promotion",
    }
)
TARGET_AUDIENCES = frozenset(
    {
        "all_subscribers",
        "new_subscribers",
        "existing_customers",
        "lapsed_buyers",
        "vip_customers",
    }
)
TONES = frozenset(
    {
        "urgent_fomo",
        "warm_inviting",
        "bold_energetic",
        "playful_fun",
        "premium_elevated",
    }
)
DISCOUNT_TYPES = frozenset(
    {
        "percentage",
        "fixed_amount",
        "bogo",
        "free_shipping",
        "bundle_deal",
        "tiered",
        "none",
    }
)
PRODUCT_FOCUS = frozenset(
    {
        "beef_crisps",
        "pork_crisps",
        "crispy_beef_bits",
        "beef_bits",
        "honey_butter_pork_jerky",
        "variety_packs",
        "all",
    }
)
SELECTION_CRITERIA = frozenset(
    {
        "best_sellers",
        "newest",
        "highest_margin",
        "seasonal_fit",
        "variety_across_flavors",
    }
)
CTA_DESTINATIONS = frozenset(
    {
        "homepage",
        "collection_page",
        "specific_product",
        "custom_url",
    }
)


def _template_path() -> Path:
    return config.root() / "questionnaire_template.yaml"


def create_template(output_path: Path) -> Path:
    """Copy bundled template to ``output_path``."""
    src = _template_path()
    if not src.is_file():
        raise FileNotFoundError(f"Missing template: {src}")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, output_path)
    return output_path


def _nonempty_str(v: Any, field: str, errors: List[str]) -> str:
    if v is None:
        errors.append(f"{field}: required non-empty string")
        return ""
    s = str(v).strip()
    if not s:
        errors.append(f"{field}: required non-empty string")
    return s


def _one_of(v: Any, field: str, allowed: frozenset, errors: List[str]) -> str:
    if v is None or (isinstance(v, str) and not v.strip()):
        errors.append(f"{field}: required; expected one of: {', '.join(sorted(allowed))}")
        return ""
    s = str(v).strip()
    if s not in allowed:
        errors.append(
            f"{field}: invalid value {s!r}; expected one of: {', '.join(sorted(allowed))}"
        )
    return s


def _coerce_bool(v: Any, default: bool = True) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        low = v.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return bool(v)


def load(path: Path) -> Dict[str, Any]:
    """Load YAML questionnaire and validate. Raises ``ValueError`` on failure."""
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Questionnaire not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ValueError("Questionnaire root must be a mapping (YAML object)")

    errors: List[str] = []

    email_theme = _nonempty_str(raw.get("email_theme"), "email_theme", errors)
    primary_goal = _one_of(raw.get("primary_goal"), "primary_goal", PRIMARY_GOALS, errors)
    target_audience = _one_of(
        raw.get("target_audience"), "target_audience", TARGET_AUDIENCES, errors
    )
    tone = _one_of(raw.get("tone"), "tone", TONES, errors)
    key_message = _nonempty_str(raw.get("key_message"), "key_message", errors)
    discount_type = _one_of(raw.get("discount_type"), "discount_type", DISCOUNT_TYPES, errors)
    product_focus = _one_of(raw.get("product_focus"), "product_focus", PRODUCT_FOCUS, errors)
    cta_destination = _one_of(
        raw.get("cta_destination"), "cta_destination", CTA_DESTINATIONS, errors
    )

    discount_value_raw = raw.get("discount_value")
    discount_value = ""
    if discount_type and discount_type not in ("none", "tiered"):
        if discount_value_raw is None or not str(discount_value_raw).strip():
            errors.append(
                "discount_value: required when discount_type is not 'none' or 'tiered' (e.g. '20%' or '$5 off')"
            )
        else:
            discount_value = str(discount_value_raw).strip()
    elif discount_type == "tiered":
        discount_value = str(discount_value_raw or "").strip()

    num_raw = raw.get("num_featured_products", 3)
    try:
        num_featured_products = int(num_raw)
    except (TypeError, ValueError):
        num_featured_products = -1
        errors.append("num_featured_products: must be an integer between 1 and 6")
    else:
        if not 1 <= num_featured_products <= 6:
            errors.append("num_featured_products: must be an integer between 1 and 6")

    cta_specific = str(raw.get("cta_specific_product") or "").strip()
    if cta_destination == "specific_product" and not cta_specific:
        errors.append(
            "cta_specific_product: required when cta_destination is 'specific_product'"
        )

    cta_custom = str(raw.get("cta_custom_url") or "").strip()
    if cta_destination == "custom_url" and not cta_custom:
        errors.append("cta_custom_url: required when cta_destination is 'custom_url'")

    selection_criteria = str(raw.get("selection_criteria") or "best_sellers").strip()
    if not selection_criteria:
        selection_criteria = "best_sellers"
    if selection_criteria not in SELECTION_CRITERIA:
        errors.append(
            f"selection_criteria: invalid value {selection_criteria!r}; "
            f"expected one of: {', '.join(sorted(SELECTION_CRITERIA))}"
        )

    featured = raw.get("featured_products")
    if featured is None:
        featured_products: List[str] = []
    elif isinstance(featured, list):
        featured_products = [str(x).strip() for x in featured if str(x).strip()]
    else:
        errors.append("featured_products: must be a list of strings (or empty)")
        featured_products = []

    if errors:
        raise ValueError("Invalid questionnaire:\n- " + "\n- ".join(errors))

    # --- Sequence config (optional, no validation errors) ---
    seq_num_raw = raw.get("sequence_num_emails", 1)
    try:
        sequence_num_emails = max(1, int(seq_num_raw))
    except (TypeError, ValueError):
        sequence_num_emails = 1

    sequence_emails_raw = raw.get("sequence_emails") or []
    sequence_emails = []
    if isinstance(sequence_emails_raw, list):
        for item in sequence_emails_raw:
            if isinstance(item, dict):
                try:
                    entry = {
                        "email_num": int(item.get("email_num", 1)),
                        "angle": str(item.get("angle") or "").strip(),
                        "send_day": int(item.get("send_day", 0)),
                        "featured_products": [
                            str(x).strip()
                            for x in (item.get("featured_products") or [])
                            if str(x).strip()
                        ],
                        "product_focus": str(item.get("product_focus") or "").strip(),
                    }
                    sequence_emails.append(entry)
                except (TypeError, ValueError):
                    pass

    out: Dict[str, Any] = {
        "email_theme": email_theme,
        "primary_goal": primary_goal,
        "target_audience": target_audience,
        "tone": tone,
        "key_message": key_message,
        "seasonal_hook": str(raw.get("seasonal_hook") or "").strip(),
        "urgency": str(raw.get("urgency") or "").strip(),
        "discount_type": discount_type,
        "discount_value": discount_value if discount_type not in ("none", "tiered") else str(
            discount_value_raw or ""
        ).strip(),
        "discount_tiers": raw.get("discount_tiers") or [],
        "discount_conditions": str(raw.get("discount_conditions") or "").strip(),
        "generate_discount_code": _coerce_bool(raw.get("generate_discount_code"), True),
        "product_focus": product_focus,
        "num_featured_products": num_featured_products,
        "featured_products": featured_products,
        "selection_criteria": selection_criteria or "best_sellers",
        "cta_destination": cta_destination,
        "cta_specific_product": cta_specific,
        "cta_custom_url": cta_custom,
        "additional_notes": str(raw.get("additional_notes") or "").strip(),
        "sequence_num_emails": sequence_num_emails,
        "sequence_emails": sequence_emails,
    }
    return out


def summarize(questionnaire: Dict[str, Any]) -> str:
    """Human-readable block for LLM context."""
    lines = [
        "CAMPAIGN QUESTIONNAIRE SUMMARY",
        "==============================",
        f"Theme: {questionnaire['email_theme']}",
        f"Goal: {questionnaire['primary_goal']}",
        f"Audience: {questionnaire['target_audience']}",
        f"Tone: {questionnaire['tone']}",
        f"Key Message: {questionnaire['key_message']}",
    ]
    hook = questionnaire.get("seasonal_hook") or ""
    if hook:
        lines.append(f"Seasonal Hook: {hook}")
    urg = questionnaire.get("urgency") or ""
    if urg:
        lines.append(f"Urgency: {urg}")

    dt = questionnaire["discount_type"]
    if dt == "none":
        disc = "none"
    elif dt == "tiered":
        tiers = questionnaire.get("discount_tiers") or []
        if tiers:
            tier_parts = [t.get("label", f"{t.get('percentage')}% off ${t.get('threshold')}+") for t in tiers]
            disc = "tiered: " + " | ".join(tier_parts)
        else:
            disc = "tiered (no tiers specified)"
    else:
        val = (questionnaire.get("discount_value") or "").strip()
        cond = (questionnaire.get("discount_conditions") or "").strip()
        parts = [val, dt]
        disc = " ".join(p for p in parts if p).strip()
        if cond:
            disc = f"{disc} ({cond})".strip() if disc else f"({cond})"
    code_note = (
        "[code will be auto-generated]"
        if questionnaire.get("generate_discount_code")
        else "[no auto-generated code]"
    )
    lines.append(f"Discount: {disc} {code_note}".strip())

    n = questionnaire["num_featured_products"]
    crit = questionnaire.get("selection_criteria") or "best_sellers"
    fp = questionnaire.get("featured_products") or []
    pf = questionnaire["product_focus"]
    if fp:
        lines.append(
            f"Product Focus: {pf} ({n} featured; specified: {', '.join(fp)})"
        )
    else:
        lines.append(f"Product Focus: {pf} ({n} featured, selected by: {crit})")

    lines.append(f"CTA Destination: {questionnaire['cta_destination']}")
    notes = questionnaire.get("additional_notes") or ""
    if notes:
        lines.append(f"Additional Notes: {notes}")

    seq_n = questionnaire.get("sequence_num_emails", 1)
    if seq_n > 1:
        lines.append(f"\nEMAIL SEQUENCE: {seq_n} emails")
        for email in questionnaire.get("sequence_emails", []):
            num = email.get("email_num", "?")
            angle = email.get("angle", "")
            day = email.get("send_day", 0)
            fps = email.get("featured_products", [])
            pf = email.get("product_focus", "")
            line = f"  Email {num} (day {day})"
            if pf:
                line += f" [{pf}]"
            if angle:
                line += f": {angle}"
            if fps:
                line += f" [products: {', '.join(fps)}]"
            lines.append(line)

    return "\n".join(lines)
