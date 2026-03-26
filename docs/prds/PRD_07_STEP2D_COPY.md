# PRD 07 — Step 2D: Copy Generator Agent

## Objective

Generate all text content for the email: subject line, preheader, headlines, body copy, CTAs, bullet points, product descriptions, and legal/fine print. Uses the brief's text slot definitions, brand identity, selected products, and discount details to produce on-brand, cohesive copy.

---

## 1. File

`email_gen/pipeline/step2d_copy.py`

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Step 1 brief | `step1_brief.json` | `io_util.read_json()` |
| Step 2A structure | `step2a_structure.json` | `io_util.read_json()` — specifically `token_manifest` for copy tokens |
| Step 2B discount | `step2b_discount.json` | `io_util.read_json()` |
| Step 2C products | `step2c_products.json` | `io_util.read_json()` |
| Questionnaire | `questionnaire.yaml` | `questionnaire.load()` |
| Brand identity text | `brand/identity_text/` | `gemini_text.load_brand_identity_text()` |

---

## 3. LLM Configuration

- **Model:** `config.copy_model()` (default: `gemini-2.5-pro`)
- **System prompt:** `STEP2D_SYSTEM`

This is the most copy-quality-sensitive agent, so `gemini-2.5-pro` is the default.

---

## 4. System Prompt

```
You are an expert email copywriter for Yay's Beef Crisps, a DTC artisanal snack brand with Cambodian heritage. You write compelling, on-brand promotional email copy.

Output valid JSON only, no markdown fences.

Schema:
{
  "subject_line": "<40-60 chars, compelling, drives opens>",
  "preheader": "<40-100 chars, complements subject line, adds info>",
  "copy_by_token": {
    "<token_name>": "<the copy for this token, respecting max_chars>"
  },
  "product_copy": {
    "<product_handle>": {
      "name_display": "<how the product name appears in the email>",
      "short_description": "<1-2 sentences for the email>",
      "price_display": "<formatted price string>"
    }
  },
  "fine_print": "<legal/conditions text for the discount, if applicable>",
  "copy_rationale": "<2-3 sentences explaining the overall copy strategy>"
}

Rules:
- copy_by_token MUST include an entry for EVERY token in the manifest where source_agent is "copy"
- Respect max_chars from the brief's text_slots — this is a hard limit
- Subject line: use curiosity, benefit, or urgency — avoid spam trigger words (FREE, ACT NOW, etc.)
- Preheader: should add NEW information, not repeat the subject line
- Headlines: bold, punchy, use Yay's brand voice (heritage, texture, flavor)
- Body copy: conversational, warm, sensory language about crunch and flavor
- CTAs: action-oriented, 2-4 words (e.g., "Grab Your Crisps", "Shop The Crunch", "Taste The Legacy")
- If a discount exists, weave the code and value naturally into the copy (don't just bolt it on)
- Product descriptions should highlight what makes each product special, not generic catalog text
- fine_print should include discount conditions, expiry, and any legal requirements
- Brand voice guidelines:
  - DO: Emphasize grandmother's legacy, Cambodian heritage, crispy texture, slow-drying, protein/carb benefits, sensory language
  - DON'T: Corporate jargon, bland claims, generic snack messaging, aggressive sales tactics
  - Example phrases: "Forget chewy jerky", "shatteringly crispy", "taste the legacy", "24g protein never tasted this good"
```

---

## 5. User Prompt Construction

```python
def _build_prompt(
    brief: Dict,
    structure: Dict,
    discount: Dict,
    products: Dict,
    questionnaire: Dict,
    brand_identity: str,
) -> str:
    # Extract copy tokens from the manifest
    copy_tokens = [
        t for t in structure.get("token_manifest", [])
        if t.get("source_agent") == "copy"
    ]
    copy_tokens_text = json.dumps(copy_tokens, indent=2)

    # Extract text slots from the brief sections
    all_text_slots = []
    for section in brief.get("sections", []):
        for slot in section.get("text_slots", []):
            all_text_slots.append({
                "section": section["id"],
                "slot_id": slot["slot_id"],
                "role": slot["role"],
                "max_chars": slot["max_chars"],
                "guidance": slot["guidance"],
            })
    text_slots_text = json.dumps(all_text_slots, indent=2)

    # Format products
    featured = products.get("featured_products", [])
    products_text = "\n".join([
        f"- {p['title']} ({p['handle']}): {p['price']} — {p.get('short_description', '')}"
        for p in featured
    ])

    # Format discount
    discount_text = "No discount for this campaign."
    if discount.get("discount_code"):
        discount_text = (
            f"Code: {discount['discount_code']}\n"
            f"Display: {discount['display_text']}\n"
            f"Conditions: {discount.get('conditions_summary', 'None')}"
        )

    return f"""Write all email copy for this campaign.

CREATIVE CONCEPT:
{brief.get('creative_concept', '')}

TONE & VOICE:
{brief.get('tone_and_voice', '')}

SUBJECT LINE DIRECTION:
{brief.get('email_subject_line_direction', '')}

PREHEADER DIRECTION:
{brief.get('preheader_direction', '')}

URGENCY TREATMENT:
{brief.get('urgency_treatment', '')}

TEXT SLOTS (from brief — respect max_chars strictly):
{text_slots_text}

COPY TOKENS TO FILL (from HTML structure — you must provide a value for each):
{copy_tokens_text}

DISCOUNT DETAILS:
{discount_text}

FEATURED PRODUCTS:
{products_text}

BRAND IDENTITY:
{brand_identity[:8000]}

QUESTIONNAIRE CONTEXT:
- Theme: {questionnaire.get('email_theme', '')}
- Key message: {questionnaire.get('key_message', '')}
- Seasonal hook: {questionnaire.get('seasonal_hook', '')}

Generate all copy per the system schema. Every copy token must be filled.
"""
```

---

## 6. Function Signature

```python
def run(run_dir: Path) -> Dict[str, Any]:
    """
    Load all prior step artifacts, call LLM, return copy dict.
    Depends on: step1, step2a, step2b, step2c.
    """
```

---

## 7. Output

Written to `output/<run_id>/step2d_copy.json`.

### Example Output (abbreviated)

```json
{
  "subject_line": "Your BBQ Is Missing Something Crispy 🔥 20% Off Inside",
  "preheader": "Shatteringly crispy beef crisps — not your average jerky. Code: YAYBBQ20",
  "copy_by_token": {
    "hero_headline": "UPGRADE YOUR BBQ GAME",
    "hero_subheadline": "20% off the crispiest snack you've never tried",
    "benefits_heading": "WHY YAY'S HITS DIFFERENT",
    "benefits_bullets": "<li>Shatteringly crispy — like a chip, not chewy jerky</li><li>24g protein, just 7g carbs per bag</li><li>Slow-dried 24 hours, never fried</li><li>Grandma's 30-year Cambodian recipe</li>",
    "cta_primary_text": "GRAB YOUR CRISPS",
    "cta_secondary_text": "SEE ALL FLAVORS",
    "closing_copy": "Life's too short for boring snacks. Taste the legacy.",
    "footer_tagline": "Taste the legacy. Crafted with love."
  },
  "product_copy": {
    "spicy-yays-beef-crisps": {
      "name_display": "Spicy Beef Crisps",
      "short_description": "For the bold ones. Extra spicy, perfectly salty, impossibly crispy.",
      "price_display": "From $18"
    },
    "original-mild-yays-beef-crisps": {
      "name_display": "Original Mild Crisps",
      "short_description": "Where it all started. Sweet, savory, and just a kiss of spice.",
      "price_display": "From $18"
    },
    "teriyaki-yays-beef-crisps": {
      "name_display": "Teriyaki Beef Crisps",
      "short_description": "Umami meets crunch. Gluten-free, 28g protein.",
      "price_display": "From $18"
    }
  },
  "fine_print": "Use code YAYBBQ20 at checkout. Valid for first-time orders only. Expires 03/26/2026. Cannot be combined with other offers.",
  "copy_rationale": "Led with the BBQ angle to match the seasonal hook, using 'upgrade' language to position Yay's as the unexpected premium addition. Wove the discount naturally into the hero subheadline and preheader. Emphasized texture differentiation ('not chewy jerky') as the primary hook since it's the strongest USP."
}
```

---

## 8. Validation

After LLM response:
1. Verify every token from the `token_manifest` (where `source_agent == "copy"`) has a corresponding entry in `copy_by_token`
2. Verify `subject_line` is 40-100 chars
3. Verify `preheader` is 40-130 chars
4. Log warnings for any copy that exceeds `max_chars` from the text slots (but don't fail — the cohesion agent will catch it)

---

## 9. Test Checkpoint

1. Run `python main.py step2d --run <run_id>` (requires steps 1, 2a, 2b, 2c)
2. Inspect `step2d_copy.json`:
   - `subject_line` and `preheader` are compelling and appropriate length
   - `copy_by_token` has an entry for every copy token in the structure's manifest
   - Copy respects `max_chars` from the brief
   - Discount code is woven into copy naturally (not just appended)
   - Product descriptions are specific to each product, not generic
   - Brand voice is authentic (heritage, texture, sensory language)
   - No spam trigger words in subject line
