"""Step 2C: Product Selector — choose products to feature from Shopify catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import anthropic_text, config, gemini_text, io_util, questionnaire as questionnaire_module, shopify_client


def _generate_text(prompt: str, model: str, system: str) -> str:
    if model.startswith("claude-"):
        return anthropic_text.generate_text(prompt=prompt, model=model, system=system)
    return gemini_text.generate_text(prompt=prompt, model=model, system=system)

STEP2C_SYSTEM = """You are a product merchandising specialist for a DTC snack brand. You select which products to feature in promotional emails based on campaign goals, audience, and product catalog data.

Output valid JSON only, no markdown fences.

Schema:
{
  "featured_products": [
    {
      "shopify_product_id": <number>,
      "title": "<product title>",
      "handle": "<product handle/slug>",
      "product_type": "<e.g. Beef Crisp>",
      "variant_id": <number>,
      "variant_title": "<e.g. Default Title, 3 Pack>",
      "sku": "<e.g. YOS3>",
      "price": "<e.g. $49.00>",
      "primary_image_url": "<Shopify CDN URL of the best product image>",
      "short_description": "<1 sentence product description for the email>",
      "selection_reason": "<why this product was chosen for this campaign>",
      "in_stock": <true|false>
    }
  ],
  "selection_strategy": "<2-3 sentences explaining the overall product selection logic>",
  "category_breakdown": "<what categories/flavors are represented and why>"
}

Rules:
- Select exactly the number of products specified in num_featured
- If specific_products are listed in the brief, those MUST be included (fill remaining slots with best matches)
- ONLY select products that are IN STOCK (check the stock status in the catalog data)
- For "best_sellers" criteria: prioritize variety packs and multi-packs (higher AOV), then single packs of popular flavors
- For "newest" criteria: prioritize products with "NEW!" in the title
- For "variety_across_flavors" criteria: ensure different flavors are represented
- primary_image_url should be the first/hero image (position 1) from the Shopify product
- price should be the variant price formatted with $ sign
- short_description should be compelling email copy, not the full Shopify description
- If product_focus is a specific category, only select from that category's product_type
- Product types in the catalog: "Beef Crisp", "Pork Crisps", "Crispy Beef Bits", "Merch"
- Include the in_stock boolean in your response for each product"""


def _format_products_for_prompt(products: List[Dict[str, Any]]) -> str:
    """Format product catalog for LLM prompt."""
    lines = []
    for p in products:
        lines.append(f"\nPRODUCT: \"{p.get('title', 'Untitled')}\" (ID: {p.get('id', 0)})")
        lines.append(f"  Type: {p.get('product_type', 'N/A')} | Handle: {p.get('handle', '')}")
        lines.append("  Variants:")
        for v in p.get("variants", [])[:5]:
            price = v.get("price", "0.00")
            stock_status = "IN STOCK" if v.get("in_stock", True) else "OUT OF STOCK"
            qty = v.get("inventory_quantity")
            qty_str = f" (qty: {qty})" if qty is not None else ""
            lines.append(f"    - \"{v.get('title', '')}\" | SKU: {v.get('sku', '')} | ${price} | {stock_status}{qty_str} (variant_id: {v.get('id', 0)})")
        images = p.get("images", [])
        if images:
            lines.append(f"  Images: {len(images)} available, hero: {images[0].get('src', '')}")
        lines.append("---")
    return "\n".join(lines)


def _build_prompt(brief: Dict, questionnaire: Dict, products: List[Dict], brand_identity: str) -> str:
    product_req = brief.get("product_requirements", {})
    products_summary = _format_products_for_prompt(products)

    return f"""Select products to feature in this email campaign.

PRODUCT REQUIREMENTS (from brief):
- Focus category: {product_req.get('focus_category', 'all')}
- Number to feature: {product_req.get('num_featured', 3)}
- Selection criteria: {product_req.get('selection_criteria', 'best_sellers')}
- Specific products requested: {product_req.get('specific_products', [])}
- How they appear: {product_req.get('how_products_appear', 'grid')}

CAMPAIGN CONTEXT:
- Theme: {questionnaire.get('email_theme', '')}
- Goal: {questionnaire.get('primary_goal', '')}
- Audience: {questionnaire.get('target_audience', '')}
- Key message: {questionnaire.get('key_message', '')}

BRAND IDENTITY:
{brand_identity[:4000]}

AVAILABLE PRODUCTS FROM SHOPIFY:
{products_summary[:8000]}

Select the best {product_req.get('num_featured', 3)} products and return JSON per schema."""


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
            "featured_products": [],
            "selection_strategy": "",
            "category_breakdown": "",
        }


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Select products from Shopify catalog."""
    full_brief = io_util.read_json(run_dir / io_util.STEP1)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    # In sequence mode, use the per-email brief section
    if total_emails > 1:
        emails = full_brief.get("emails") or []
        idx = email_num - 1
        brief = emails[idx] if 0 <= idx < len(emails) else full_brief
    else:
        brief = full_brief

    all_products = shopify_client.get_products(limit=50)

    product_req = brief.get("product_requirements", {})
    focus = product_req.get("focus_category", "all")
    if focus != "all":
        category_type_map = {
            "beef_crisps": "Beef Crisp",
            "pork_crisps": "Pork Crisps",
            "crispy_beef_bits": "Crispy Beef Bits",
            "beef_bits": "Crispy Beef Bits",
            "honey_butter_pork_jerky": "Pork Crisps",
            "variety_packs": "Variety Pack",
        }
        target_type = category_type_map.get(focus)
        if target_type:
            filtered = [p for p in all_products if p.get("product_type") == target_type]
            if filtered:
                all_products = filtered

    pc = focus if focus != "all" else None
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)

    # Collect product IDs already featured in earlier emails to avoid repetition
    already_featured_ids: List[int] = []
    if email_num > 1:
        for prev_num in range(1, email_num):
            prev_path = run_dir / io_util.step_filename(io_util.STEP2C, prev_num, total_emails)
            if prev_path.is_file():
                prev_data = io_util.read_json(prev_path)
                for p in prev_data.get("featured_products", []):
                    pid = p.get("shopify_product_id")
                    if pid:
                        already_featured_ids.append(int(pid))

    prompt = _build_prompt(brief, questionnaire, all_products, brand_identity)

    # Append "do not repeat" context for emails after the first
    if already_featured_ids:
        prompt += (
            f"\n\nSEQUENCE NOTE: This is email {email_num} of {total_emails}. "
            f"The following Shopify product IDs were already featured in earlier emails — "
            f"do NOT select them again unless explicitly required by specific_products: "
            f"{already_featured_ids}"
        )

    raw = _generate_text(prompt=prompt, model=config.products_model(), system=STEP2C_SYSTEM)

    data = _parse_json(raw)
    data.setdefault("featured_products", [])
    data.setdefault("selection_strategy", "")
    data.setdefault("category_breakdown", "")

    # Flag products that have same-type siblings in the catalog (potential duplicates)
    for selected in data["featured_products"]:
        sel_type = selected.get("product_type", "")
        sel_title = selected.get("title", "").lower()
        sel_id = selected.get("shopify_product_id")
        siblings = [
            p.get("handle", "")
            for p in all_products
            if p.get("product_type") == sel_type
            and p.get("id") != sel_id
            and sel_title[:10] in p.get("title", "").lower()
        ]
        if siblings:
            selected["has_catalog_siblings"] = True
            selected["sibling_handles"] = siblings
        else:
            selected["has_catalog_siblings"] = False

    output_filename = io_util.step_filename(io_util.STEP2C, email_num, total_emails)
    io_util.write_json(run_dir / output_filename, data)
    return data
