"""Step 2B: Discount Strategy — generate discount code and create in Shopify."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

from . import anthropic_text, config, gemini_text, io_util, questionnaire as questionnaire_module, shopify_client


def _generate_text(prompt: str, model: str, system: str) -> str:
    if model.startswith("claude-"):
        return anthropic_text.generate_text(prompt=prompt, model=model, system=system)
    return gemini_text.generate_text(prompt=prompt, model=model, system=system)

STEP2B_SYSTEM = """You are a DTC e-commerce discount strategist. You create discount codes and pricing strategies for email campaigns.

Output valid JSON only, no markdown fences.

Schema:
{
  "discount_code": "<the code customers will enter, e.g. YAYBBQ20>",
  "display_text": "<how the discount appears in the email, e.g. '20% OFF with code YAYBBQ20'>",
  "value_type": "<percentage|fixed_amount>",
  "value": "<negative number as string, e.g. '-20.0' or '-5.00'>",
  "target_type": "<line_item|shipping_line>",
  "target_selection": "<all|entitled>",
  "allocation_method": "<across|each>",
  "customer_selection": "<all|prerequisite>",
  "once_per_customer": <true|false>,
  "usage_limit": <null or number>,
  "starts_at": "<ISO 8601 datetime>",
  "ends_at": "<ISO 8601 datetime or null>",
  "conditions_summary": "<human-readable conditions for the email copy>",
  "naming_rationale": "<why this code name was chosen>"
}

Rules:
- Code should be memorable, brand-relevant, and easy to type (ALL CAPS, no special chars)
- Code length: 6-12 characters
- If discount_type is "none", return {"discount_code": null, "display_text": "No discount for this campaign", ...} with null/empty values
- If discount_type is "tiered", the discount_tiers array contains the tier structure. Set display_text to show all tiers clearly (e.g. "10% off $100+ | 15% off $150+ | 20% off $200+"). Set value/value_type based on the middle or highest tier as a representative for Shopify (since Shopify price rules don't natively support tiered — the actual tiers will be applied manually). Set conditions_summary to spell out all tiers for the email fine print.
- If discount_type is "bogo" or "bundle_deal", use appropriate Shopify price rule configuration
- If discount_type is "free_shipping", set target_type to "shipping_line"
- starts_at should be now (or the campaign date), ends_at based on urgency"""


def _build_prompt(discount_req: Dict[str, Any], questionnaire: Dict[str, Any]) -> str:
    tiers_block = ""
    if questionnaire.get("discount_type") == "tiered":
        tiers = questionnaire.get("discount_tiers") or []
        if tiers:
            tiers_block = f"\nTIERED DISCOUNT STRUCTURE:\n{json.dumps(tiers, indent=2)}\n"

    return f"""Create a discount strategy for this email campaign.

DISCOUNT REQUIREMENTS (from brief):
{json.dumps(discount_req, indent=2)}
{tiers_block}
CAMPAIGN CONTEXT:
- Theme: {questionnaire.get('email_theme', '')}
- Urgency: {questionnaire.get('urgency', '')}
- Audience: {questionnaire.get('target_audience', '')}

Generate the discount code and Shopify price rule configuration per the schema."""


def _parse_json(response: str) -> Dict[str, Any]:
    """Parse LLM JSON response with fallback."""
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
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "parse_error": True,
            "raw_response": response[:1000],
            "discount_code": None,
            "display_text": "",
        }


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Generate discount strategy and create in Shopify.

    For sequences (total_emails > 1), the discount code is shared across all emails.
    Only email 1 generates a new code; subsequent emails reuse the existing one.
    """
    if email_num > 1:
        # Reuse the discount code created for email 1
        return io_util.read_json(run_dir / io_util.STEP2B)

    full_brief = io_util.read_json(run_dir / io_util.STEP1)
    # In sequence mode, use the first email's discount_requirements from the brief
    if total_emails > 1:
        emails = full_brief.get("emails") or []
        brief = emails[0] if emails else full_brief
    else:
        brief = full_brief
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    discount_req = brief.get("discount_requirements", {})

    if discount_req.get("type") == "none" or questionnaire.get("discount_type") == "none":
        result = {
            "discount_code": None,
            "display_text": "No discount for this campaign",
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
            "shopify_created": False,
        }
        io_util.write_json(run_dir / io_util.STEP2B, result)
        return result

    prompt = _build_prompt(discount_req, questionnaire)
    raw = _generate_text(
        prompt=prompt,
        model=config.discount_model(),
        system=STEP2B_SYSTEM,
    )

    strategy = _parse_json(raw)
    strategy.setdefault("discount_code", "YAYSALE")
    strategy.setdefault("display_text", "Discount available")
    strategy.setdefault("value_type", "percentage")
    strategy.setdefault("value", "-10.0")
    strategy.setdefault("target_type", "line_item")
    strategy.setdefault("target_selection", "all")
    strategy.setdefault("allocation_method", "across")
    strategy.setdefault("customer_selection", "all")
    strategy.setdefault("once_per_customer", True)
    strategy.setdefault("usage_limit", None)
    strategy.setdefault("starts_at", datetime.now(timezone.utc).isoformat())
    strategy.setdefault("ends_at", None)

    if questionnaire.get("generate_discount_code"):
        try:
            price_rule = shopify_client.create_price_rule({
                "title": strategy["discount_code"],
                "target_type": strategy["target_type"],
                "target_selection": strategy["target_selection"],
                "allocation_method": strategy["allocation_method"],
                "value_type": strategy["value_type"],
                "value": strategy["value"],
                "customer_selection": strategy["customer_selection"],
                "once_per_customer": strategy.get("once_per_customer", True),
                "usage_limit": strategy.get("usage_limit"),
                "starts_at": strategy["starts_at"],
                "ends_at": strategy.get("ends_at"),
            })

            discount_code = shopify_client.create_discount_code(
                price_rule["id"],
                strategy["discount_code"],
            )

            strategy["shopify_price_rule_id"] = price_rule["id"]
            strategy["shopify_discount_code_id"] = discount_code["id"]
            strategy["shopify_created"] = True

        except Exception as e:
            suffix = random.randint(10, 99)
            strategy["discount_code"] = f"{strategy['discount_code']}{suffix}"
            strategy["shopify_created"] = False
            strategy["shopify_error"] = str(e)
    else:
        strategy["shopify_created"] = False

    io_util.write_json(run_dir / io_util.STEP2B, strategy)
    return strategy
