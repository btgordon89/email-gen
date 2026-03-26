# PRD 05 — Step 2B: Discount Strategy Agent

## Objective

Take the discount requirements from the Step 1 brief, generate a discount code name, and create a real discount code in Shopify via the Admin API. Returns the discount details for use by the copy and link agents.

---

## 1. Files

- `email_gen/pipeline/step2b_discount.py` — Agent logic
- `email_gen/pipeline/shopify_client.py` — Shopify Admin API client (shared with Steps 2C and 2E)

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Step 1 brief | `output/<run_id>/step1_brief.json` | `io_util.read_json()` |
| Questionnaire | `output/<run_id>/questionnaire.yaml` | `questionnaire.load()` |

Specifically uses:
- `brief["discount_requirements"]` — type, value, conditions, code_needed, code_naming_direction
- `questionnaire["discount_type"]`, `questionnaire["discount_value"]`, `questionnaire["discount_conditions"]`

---

## 3. shopify_client.py — Shared Shopify Admin API Client

### Shopify Credentials

From `.env` (already exists):
```
SHOPIFY_SHOP_URL=yays-snacks.myshopify.com
SHOPIFY_ADMIN_API_TOKEN=your_shopify_admin_api_token_here
```

### API Base URL

```
https://{SHOPIFY_SHOP_URL}/admin/api/2024-01/
```

### Authentication

All requests include header:
```
X-Shopify-Access-Token: {SHOPIFY_ADMIN_API_TOKEN}
Content-Type: application/json
```

### Functions

#### `get_products(limit=50) -> List[Dict]`
```
GET /admin/api/2024-01/products.json?limit={limit}&status=active
```
Returns list of product dicts with: id, title, handle, product_type, variants (id, title, sku, price), images (id, src, alt, position).

#### `get_product_by_handle(handle: str) -> Optional[Dict]`
```
GET /admin/api/2024-01/products.json?handle={handle}
```

#### `get_collections() -> List[Dict]`
```
GET /admin/api/2024-01/custom_collections.json
GET /admin/api/2024-01/smart_collections.json
```
Merge both lists. Returns id, title, handle for each.

#### `create_price_rule(price_rule: Dict) -> Dict`
```
POST /admin/api/2024-01/price_rules.json
Body: { "price_rule": { ... } }
```

#### `create_discount_code(price_rule_id: int, code: str) -> Dict`
```
POST /admin/api/2024-01/price_rules/{price_rule_id}/discount_codes.json
Body: { "discount_code": { "code": "{code}" } }
```

#### `get_shop_url() -> str`
Returns the public storefront URL: `https://snackyays.com` (or constructs from `SHOPIFY_SHOP_URL`).

### Price Rule Schema (for reference)

```json
{
  "price_rule": {
    "title": "YAYBBQ20",
    "target_type": "line_item",
    "target_selection": "all",
    "allocation_method": "across",
    "value_type": "percentage",
    "value": "-20.0",
    "customer_selection": "all",
    "starts_at": "2026-03-20T00:00:00Z",
    "usage_limit": null,
    "once_per_customer": true
  }
}
```

For `value_type`:
- `"percentage"` → `value` is negative percentage (e.g., `"-20.0"`)
- `"fixed_amount"` → `value` is negative dollar amount (e.g., `"-5.00"`)

For BOGO / free shipping, different `target_type` and `allocation_method` values apply — the LLM agent will determine the correct configuration.

---

## 4. LLM Configuration (step2b_discount.py)

- **Model:** `config.discount_model()` (default: `gemini-2.5-flash`)
- **System prompt:** `STEP2B_SYSTEM`

---

## 5. System Prompt

```
You are a DTC e-commerce discount strategist. You create discount codes and pricing strategies for email campaigns.

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
- If discount_type is "bogo" or "bundle_deal", use appropriate Shopify price rule configuration
- If discount_type is "free_shipping", set target_type to "shipping_line"
- starts_at should be now (or the campaign date), ends_at based on urgency
```

---

## 6. Agent Flow

```python
def run(run_dir: Path) -> Dict[str, Any]:
    brief = io_util.read_json(run_dir / io_util.STEP1)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    discount_req = brief.get("discount_requirements", {})

    if discount_req.get("type") == "none" or questionnaire.get("discount_type") == "none":
        return {
            "discount_code": None,
            "display_text": "No discount for this campaign",
            "shopify_price_rule_id": None,
            "shopify_discount_code_id": None,
        }

    # 1. Call LLM to generate discount strategy
    strategy = _generate_strategy(discount_req, questionnaire)

    # 2. Create price rule in Shopify
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

    # 3. Create discount code under that price rule
    discount_code = shopify_client.create_discount_code(
        price_rule["id"],
        strategy["discount_code"],
    )

    # 4. Return combined result
    return {
        **strategy,
        "shopify_price_rule_id": price_rule["id"],
        "shopify_discount_code_id": discount_code["id"],
    }
```

---

## 7. Output

Written to `output/<run_id>/step2b_discount.json`.

Key fields consumed by downstream agents:
- `discount_code` — used by copy agent (2D) and link agent (2E)
- `display_text` — used by copy agent (2D) for email text
- `conditions_summary` — used by copy agent (2D) for fine print

---

## 8. Error Handling

- If Shopify API returns an error (e.g., duplicate code), append a random 2-digit suffix and retry once
- If Shopify is unreachable, store the strategy JSON with `"shopify_created": false` and a warning message — the pipeline can continue, and the code can be created manually
- Log all Shopify API responses for debugging

---

## 9. Test Checkpoint

1. Run `python main.py step2b --run <run_id>`
2. Inspect `step2b_discount.json`:
   - `discount_code` is a valid, memorable code
   - `display_text` is human-readable
   - `shopify_price_rule_id` is a real Shopify ID
3. Verify in Shopify admin (or via API) that the price rule and discount code exist
4. Test with `discount_type: "none"` — should return null code without calling Shopify
