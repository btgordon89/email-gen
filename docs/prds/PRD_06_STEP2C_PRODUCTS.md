# PRD 06 — Step 2C: Product Selector Agent

## Objective

Pull live product data from the Shopify Admin API, cross-reference with the brief's product requirements, and select the products to feature in the email. Returns structured product data including titles, prices, image URLs, handles, and variant IDs.

---

## 1. File

`email_gen/pipeline/step2c_products.py`

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Step 1 brief | `output/<run_id>/step1_brief.json` | `io_util.read_json()` |
| Questionnaire | `output/<run_id>/questionnaire.yaml` | `questionnaire.load()` |
| Live Shopify products | Shopify Admin API | `shopify_client.get_products()` |
| Brand identity text | `brand/identity_text/` | `gemini_text.load_brand_identity_text()` |

Specifically uses:
- `brief["product_requirements"]` — focus_category, num_featured, selection_criteria, specific_products, how_products_appear
- `questionnaire["product_focus"]`, `questionnaire["featured_products"]`, `questionnaire["selection_criteria"]`

---

## 3. LLM Configuration

- **Model:** `config.products_model()` (default: `gemini-2.5-flash`)
- **System prompt:** `STEP2C_SYSTEM`

---

## 4. System Prompt

```
You are a product merchandising specialist for a DTC snack brand. You select which products to feature in promotional emails based on campaign goals, audience, and product catalog data.

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
      "selection_reason": "<why this product was chosen for this campaign>"
    }
  ],
  "selection_strategy": "<2-3 sentences explaining the overall product selection logic>",
  "category_breakdown": "<what categories/flavors are represented and why>"
}

Rules:
- Select exactly the number of products specified in num_featured
- If specific_products are listed in the brief, those MUST be included (fill remaining slots with best matches)
- For "best_sellers" criteria: prioritize variety packs and multi-packs (higher AOV), then single packs of popular flavors
- For "newest" criteria: prioritize products with "NEW!" in the title
- For "variety_across_flavors" criteria: ensure different flavors are represented
- primary_image_url should be the first/hero image (position 1) from the Shopify product
- price should be the variant price formatted with $ sign
- short_description should be compelling email copy, not the full Shopify description
- If product_focus is a specific category, only select from that category's product_type
- Product types in the catalog: "Beef Crisp", "Pork Crisps", "Crispy Beef Bits", "Merch"
```

---

## 5. User Prompt Construction

```python
def _build_prompt(brief: Dict, questionnaire: Dict, products: List[Dict], brand_identity: str) -> str:
    product_req = brief.get("product_requirements", {})
    products_summary = _format_products_for_prompt(products)  # Compact summary of all Shopify products

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
{products_summary}

Select the best {product_req.get('num_featured', 3)} products and return JSON per schema.
"""
```

### Product Summary Format

The `_format_products_for_prompt` function condenses the Shopify product list:

```
PRODUCT: "Spicy Yay's Beef Crisps" (ID: 8494862139699)
  Type: Beef Crisp | Handle: spicy-yays-beef-crisps
  Variants:
    - "1 Pack" | SKU: YOS1 | $18.00 (variant_id: 46100959035699)
    - "3 Pack" | SKU: YOS3 | $49.00 (variant_id: 46100959068467)
    - "6 Pack" | SKU: YOS6 | $89.99 (variant_id: 46100959101235)
  Images: 7 available, hero: https://cdn.shopify.com/...
---
PRODUCT: "NEW! Crispy Beef Bits - Spicy" (ID: ...)
  ...
```

---

## 6. Agent Flow

```python
def run(run_dir: Path) -> Dict[str, Any]:
    brief = io_util.read_json(run_dir / io_util.STEP1)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    # Fetch live products from Shopify
    all_products = shopify_client.get_products(limit=50)

    # Filter by category if specified
    product_req = brief.get("product_requirements", {})
    focus = product_req.get("focus_category", "all")
    if focus != "all":
        category_type_map = {
            "beef_crisps": "Beef Crisp",
            "pork_crisps": "Pork Crisps",
            "crispy_beef_bits": "Crispy Beef Bits",
            "variety_packs": None,  # variety packs span types
        }
        target_type = category_type_map.get(focus)
        if target_type:
            filtered = [p for p in all_products if p.get("product_type") == target_type]
            if filtered:
                all_products = filtered

    # Load brand identity for context
    pc = focus if focus != "all" else None
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)

    # Call LLM for selection
    prompt = _build_prompt(brief, questionnaire, all_products, brand_identity)
    raw = gemini_text.generate_text(prompt, model=config.products_model(), system=STEP2C_SYSTEM)

    # Parse and validate
    data = _parse_json_response(raw)

    # Validate that selected product IDs actually exist in the catalog
    valid_ids = {p["id"] for p in all_products}
    for fp in data.get("featured_products", []):
        if fp.get("shopify_product_id") not in valid_ids:
            # LLM hallucinated a product ID — try to match by title
            matched = _fuzzy_match_product(fp.get("title", ""), all_products)
            if matched:
                fp["shopify_product_id"] = matched["id"]
                fp["handle"] = matched.get("handle", "")
                fp["primary_image_url"] = matched["images"][0]["src"] if matched.get("images") else ""

    return data
```

---

## 7. Output

Written to `output/<run_id>/step2c_products.json`.

Key fields consumed by downstream agents:
- `featured_products[].title` — used by copy agent (2D)
- `featured_products[].price` — used by copy agent (2D) and assembly (5)
- `featured_products[].primary_image_url` — used by assembly (5) for product images
- `featured_products[].handle` — used by link agent (2E) to construct product URLs
- `featured_products[].short_description` — used by copy agent (2D)

---

## 8. Test Checkpoint

1. Run `python main.py step2c --run <run_id>`
2. Inspect `step2c_products.json`:
   - `featured_products` has the correct number of items
   - Each product has a valid `shopify_product_id` that exists in the Shopify catalog
   - `primary_image_url` is a valid Shopify CDN URL
   - `price` is formatted correctly
   - Products match the focus category from the brief
3. Test with `featured_products: ["Spicy Yay's Beef Crisps"]` in questionnaire — verify it's included
