# PRD 08 — Step 2E: Link Agent

## Objective

Retrieve all URLs needed for the email CTAs and product links from the Shopify API, append discount codes as query parameters, and map each CTA to its destination URL. This agent ensures every link in the email is correct and discount-enabled.

---

## 1. File

`email_gen/pipeline/step2e_links.py`

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Step 1 brief | `step1_brief.json` | `io_util.read_json()` — specifically `cta_requirements` |
| Step 2A structure | `step2a_structure.json` | `io_util.read_json()` — specifically `token_manifest` for link tokens |
| Step 2B discount | `step2b_discount.json` | `io_util.read_json()` — specifically `discount_code` |
| Step 2C products | `step2c_products.json` | `io_util.read_json()` — specifically `featured_products[].handle` |
| Shopify collections | Shopify Admin API | `shopify_client.get_collections()` |

---

## 3. LLM Configuration

- **Model:** `config.links_model()` (default: `gemini-2.5-flash`)
- **System prompt:** `STEP2E_SYSTEM`

This agent is mostly deterministic (URL construction), but uses the LLM to resolve ambiguous CTA destinations (e.g., "beef crisps collection" → which collection handle?).

---

## 4. Storefront URL Construction

The Shopify storefront base URL is `https://snackyays.com` (the public domain, not the `.myshopify.com` admin URL).

### URL Patterns

| Destination | URL Pattern |
|-------------|-------------|
| Homepage | `https://snackyays.com/` |
| Collection page | `https://snackyays.com/collections/{collection_handle}` |
| Product page | `https://snackyays.com/products/{product_handle}` |
| Custom URL | As specified |

### Discount Code Suffix

If a discount code exists, append it as a query parameter:
```
https://snackyays.com/collections/beef-crisps?discount=YAYBBQ20
```

For URLs that already have query parameters:
```
https://snackyays.com/products/spicy?variant=123&discount=YAYBBQ20
```

---

## 5. System Prompt

```
You are a URL routing specialist for a Shopify e-commerce email campaign. You map CTA destinations to actual Shopify storefront URLs.

Output valid JSON only, no markdown fences.

Schema:
{
  "links_by_token": {
    "<token_name>": "<full URL with discount parameter>"
  },
  "product_links": {
    "<product_handle>": "<full product URL with discount parameter>"
  },
  "collection_links": {
    "<collection_handle>": "<full collection URL with discount parameter>"
  },
  "unsubscribe_link": "{{unsubscribe_url}}",
  "preferences_link": "{{preferences_url}}",
  "resolution_notes": "<how ambiguous destinations were resolved>"
}

Rules:
- links_by_token MUST include an entry for EVERY token in the manifest where source_agent is "link"
- All product/collection URLs must use the public storefront domain (https://snackyays.com), NOT the .myshopify.com admin URL
- If a discount code exists, append ?discount={code} to ALL shopping links (not unsubscribe/preferences)
- unsubscribe_link and preferences_link should use Klaviyo template tags: {{unsubscribe_url}} and {{preferences_url}} — these are replaced by Klaviyo at send time
- For "collection_page" destinations, match to the most relevant collection from the available collections list
- For "specific_product" destinations, use the product handle from the featured products
- For "homepage" destinations, use the base storefront URL
```

---

## 6. Agent Flow

```python
def run(run_dir: Path) -> Dict[str, Any]:
    brief = io_util.read_json(run_dir / io_util.STEP1)
    structure = io_util.read_json(run_dir / io_util.STEP2A)
    discount = io_util.read_json(run_dir / io_util.STEP2B)
    products = io_util.read_json(run_dir / io_util.STEP2C)

    discount_code = discount.get("discount_code")
    storefront_url = "https://snackyays.com"

    # Get link tokens from structure manifest
    link_tokens = [
        t for t in structure.get("token_manifest", [])
        if t.get("source_agent") == "link"
    ]

    # Get CTA requirements from brief
    cta_reqs = brief.get("cta_requirements", [])

    # Get featured product handles
    featured = products.get("featured_products", [])

    # Fetch collections from Shopify for resolution
    collections = shopify_client.get_collections()

    # Build product links (deterministic)
    product_links = {}
    for p in featured:
        handle = p.get("handle", "")
        url = f"{storefront_url}/products/{handle}"
        if discount_code:
            url += f"?discount={discount_code}"
        product_links[handle] = url

    # Use LLM to resolve CTA destinations to URLs
    prompt = _build_prompt(cta_reqs, link_tokens, collections, featured, discount_code, storefront_url)
    raw = gemini_text.generate_text(prompt, model=config.links_model(), system=STEP2E_SYSTEM)
    data = _parse_json_response(raw)

    # Override product_links with our deterministic ones (LLM may hallucinate handles)
    data["product_links"] = product_links

    # Ensure Klaviyo template tags for unsubscribe/preferences
    data["unsubscribe_link"] = "{{ unsubscribe_url }}"
    data["preferences_link"] = "{{ manage_subscription_url }}"

    return data
```

---

## 7. Output

Written to `output/<run_id>/step2e_links.json`.

### Example Output

```json
{
  "links_by_token": {
    "hero_cta_link": "https://snackyays.com/collections/beef-crisps?discount=YAYBBQ20",
    "secondary_cta_link": "https://snackyays.com/collections/all?discount=YAYBBQ20",
    "product_1_link": "https://snackyays.com/products/spicy-yays-beef-crisps?discount=YAYBBQ20",
    "product_2_link": "https://snackyays.com/products/original-mild-yays-beef-crisps?discount=YAYBBQ20",
    "product_3_link": "https://snackyays.com/products/teriyaki-yays-beef-crisps?discount=YAYBBQ20",
    "unsubscribe_link": "{{ unsubscribe_url }}",
    "preferences_link": "{{ manage_subscription_url }}"
  },
  "product_links": {
    "spicy-yays-beef-crisps": "https://snackyays.com/products/spicy-yays-beef-crisps?discount=YAYBBQ20",
    "original-mild-yays-beef-crisps": "https://snackyays.com/products/original-mild-yays-beef-crisps?discount=YAYBBQ20",
    "teriyaki-yays-beef-crisps": "https://snackyays.com/products/teriyaki-yays-beef-crisps?discount=YAYBBQ20"
  },
  "collection_links": {
    "beef-crisps": "https://snackyays.com/collections/beef-crisps?discount=YAYBBQ20"
  },
  "unsubscribe_link": "{{ unsubscribe_url }}",
  "preferences_link": "{{ manage_subscription_url }}",
  "resolution_notes": "Mapped 'Beef crisps collection' CTA to the 'beef-crisps' collection handle. Product CTAs mapped directly to featured product handles."
}
```

---

## 8. Test Checkpoint

1. Run `python main.py step2e --run <run_id>` (requires steps 1, 2a, 2b, 2c)
2. Inspect `step2e_links.json`:
   - Every link token from the structure manifest has a corresponding URL
   - All shopping URLs use `https://snackyays.com` (not `.myshopify.com`)
   - Discount code is appended to all shopping URLs
   - Product URLs use correct handles from the Shopify catalog
   - Unsubscribe/preferences use Klaviyo template tags
3. Manually visit a few URLs to verify they resolve (product pages exist)
