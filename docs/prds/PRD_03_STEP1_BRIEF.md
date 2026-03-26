# PRD 03 — Step 1: Brief Generator Agent

## Objective

Take the validated questionnaire and brand identity text, and produce a comprehensive email brief (JSON) that serves as the master plan for all downstream agents. This agent is the "creative director" — it doesn't write copy or build HTML, it creates the blueprint.

---

## 1. File

`email_gen/pipeline/step1_brief.py`

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Questionnaire | `output/<run_id>/questionnaire.yaml` | `questionnaire.load()` |
| Brand identity text | `brand/identity_text/` | `gemini_text.load_brand_identity_text(product_category)` where `product_category` comes from questionnaire `product_focus` (if it maps to a specific category, not "all") |

---

## 3. LLM Configuration

- **Model:** `config.brief_model()` (default: `gemini-2.5-pro`)
- **System prompt:** Defined as `STEP1_SYSTEM` constant (see below)
- **User prompt:** Constructed from questionnaire summary + brand identity

---

## 4. System Prompt

```
You are a senior email marketing strategist for a DTC food brand. You create detailed email campaign briefs that downstream specialist agents will execute.

Output valid JSON only, no markdown fences.

Schema:
{
  "creative_concept": "<2-3 sentences: the overarching creative idea that ties the email together. This guides tone, imagery, and copy direction.>",
  "email_subject_line_direction": "<1 sentence: guidance for the subject line — what angle, what emotion, what hook>",
  "preheader_direction": "<1 sentence: what the preheader text should accomplish>",
  "sections": [
    {
      "id": "<unique snake_case id, e.g. 'hero', 'benefits_grid', 'product_showcase'>",
      "type": "<one of: header, hero_banner, product_showcase, benefits_list, social_proof, cta_block, divider, footer>",
      "purpose": "<what this section accomplishes in the email flow>",
      "position": <integer, 1-based order in the email>,
      "image_required": <true|false>,
      "image_description": "<if image_required is true: detailed description of what the image should show, mood, style>",
      "text_slots": [
        {
          "slot_id": "<unique id like 'hero_headline', 'benefits_heading'>",
          "role": "<headline|subheadline|body_copy|bullet_point|cta_text|legal_text|caption>",
          "max_chars": <number>,
          "guidance": "<what this text should say/accomplish>"
        }
      ],
      "layout_notes": "<any specific layout guidance: full-width, 2-column grid, centered, etc.>"
    }
  ],
  "discount_requirements": {
    "type": "<percentage|fixed_amount|bogo|free_shipping|bundle_deal|none>",
    "value": "<e.g. '20%', '$5 off'>",
    "conditions": "<e.g. 'first order only', 'minimum $30'>",
    "code_needed": <true|false>,
    "code_naming_direction": "<e.g. 'seasonal + brand, like YAYSUMMER20'>"
  },
  "product_requirements": {
    "focus_category": "<beef_crisps|pork_crisps|crispy_beef_bits|variety_packs|all>",
    "num_featured": <number>,
    "selection_criteria": "<best_sellers|newest|highest_margin|seasonal_fit|variety_across_flavors>",
    "specific_products": ["<if user specified any>"],
    "how_products_appear": "<e.g. 'grid of 3 with images and prices', 'single hero product', 'comparison table'>"
  },
  "cta_requirements": [
    {
      "cta_id": "<e.g. 'primary_cta', 'secondary_cta', 'product_cta_1'>",
      "text_direction": "<what the CTA text should convey>",
      "destination_type": "<homepage|collection_page|specific_product|custom_url>",
      "destination_detail": "<e.g. 'beef crisps collection', 'Spicy Beef Crisps product page'>",
      "prominence": "<primary|secondary|tertiary>"
    }
  ],
  "tone_and_voice": "<2-3 sentences synthesizing the questionnaire tone with brand voice guidelines>",
  "urgency_treatment": "<how urgency should manifest in the email: countdown language, limited stock callouts, deadline mentions, or 'none'>"
}

Rules:
- sections array must have 4-8 sections (typical email structure)
- Every email MUST have at minimum: a header, a hero section, at least one CTA block, and a footer
- Each section's text_slots must have realistic max_chars (headlines 40-80, body 100-300, CTAs 15-30)
- image_description should be vivid enough for an image generation agent to work from
- discount_requirements must align with the questionnaire input
- product_requirements.specific_products should pass through any user-specified products verbatim
- cta_requirements must include at least one primary CTA
- Do NOT write the actual copy — only provide direction and constraints for the copy agent
```

---

## 5. User Prompt Construction

```python
def _build_prompt(questionnaire: Dict[str, Any], brand_identity: str) -> str:
    summary = questionnaire_module.summarize(questionnaire)
    return f"""Create a detailed email campaign brief based on this questionnaire and brand identity.

CAMPAIGN QUESTIONNAIRE:
{summary}

BRAND IDENTITY:
{brand_identity[:12000]}

Generate the brief JSON per the system schema. Make sure:
1. The creative_concept ties everything together with a clear, compelling angle
2. Sections flow logically (hook → value → proof → action)
3. Discount and product requirements faithfully reflect the questionnaire
4. Text slot guidance is specific enough for a copywriter to execute without ambiguity
5. Image descriptions are detailed enough for an AI image generator
"""
```

---

## 6. Output JSON Schema

See the schema in the system prompt above. The output is written to `output/<run_id>/step1_brief.json`.

### Example Output (abbreviated)

```json
{
  "creative_concept": "Position Yay's as the unexpected BBQ hero — the crispy, protein-packed snack that upgrades any summer gathering from ordinary to extraordinary.",
  "email_subject_line_direction": "Lead with the BBQ angle and the discount — create curiosity about what 'crispy beef' means at a BBQ",
  "preheader_direction": "Reinforce the discount and hint at the unique texture to drive opens",
  "sections": [
    {
      "id": "header",
      "type": "header",
      "purpose": "Brand recognition and navigation",
      "position": 1,
      "image_required": true,
      "image_description": "Yay's logo on a warm navy gradient background, clean and minimal",
      "text_slots": [],
      "layout_notes": "Full-width, centered logo, 60px padding top/bottom"
    },
    {
      "id": "hero",
      "type": "hero_banner",
      "purpose": "Immediate hook — communicate the offer and create desire",
      "position": 2,
      "image_required": true,
      "image_description": "Vibrant summer scene: Yay's beef crisps bags arranged on a rustic wooden table with BBQ elements (grill marks, fresh herbs, lemon slices) in warm golden-hour lighting. Brand colors (navy, gold) subtly present.",
      "text_slots": [
        {
          "slot_id": "hero_headline",
          "role": "headline",
          "max_chars": 50,
          "guidance": "Bold statement about Yay's at BBQ season — should feel exciting and unexpected"
        },
        {
          "slot_id": "hero_subheadline",
          "role": "subheadline",
          "max_chars": 80,
          "guidance": "Reinforce the discount offer and create urgency"
        }
      ],
      "layout_notes": "Full-width image with text overlay, headline in Bebas Neue, subheadline in Outfit"
    }
  ],
  "discount_requirements": {
    "type": "percentage",
    "value": "20%",
    "conditions": "First order only",
    "code_needed": true,
    "code_naming_direction": "Summer + brand themed, e.g. YAYBBQ20 or CRISPYSUMMER"
  },
  "product_requirements": {
    "focus_category": "beef_crisps",
    "num_featured": 3,
    "selection_criteria": "best_sellers",
    "specific_products": [],
    "how_products_appear": "3-column grid with product images, names, prices, and individual 'Shop Now' buttons"
  },
  "cta_requirements": [
    {
      "cta_id": "hero_cta",
      "text_direction": "Action-oriented, references the discount",
      "destination_type": "collection_page",
      "destination_detail": "Beef crisps collection",
      "prominence": "primary"
    },
    {
      "cta_id": "product_cta",
      "text_direction": "Product-specific, invites exploration",
      "destination_type": "specific_product",
      "destination_detail": "Each featured product's page",
      "prominence": "secondary"
    }
  ],
  "tone_and_voice": "Bold and energetic with warmth — channel the excitement of summer gatherings while honoring Yay's heritage story. Use vivid sensory language about crunch and flavor. Keep it conversational, not corporate.",
  "urgency_treatment": "Mention 'this weekend only' in the hero and repeat near the final CTA. No countdown timer, but language should create soft FOMO."
}
```

---

## 7. JSON Parsing & Fallback

Same pattern as `ads_gen_v2/pipeline/step1_concept.py` lines 141-200:

1. Strip the raw response
2. If it contains triple backticks, extract the JSON block
3. Try `json.loads()`
4. On `JSONDecodeError`, create a minimal fallback structure with `"parse_error": true` and the raw text stored for debugging
5. Apply `.setdefault()` for all required top-level keys

---

## 8. Function Signature

```python
def run(run_dir: Path) -> Dict[str, Any]:
    """
    Load questionnaire from run_dir, load brand identity, call LLM, return brief dict.
    """
```

---

## 9. Test Checkpoint

1. Fill out a questionnaire for a "Summer BBQ 20% off beef crisps" campaign
2. Run `python main.py step1 --run <run_id>`
3. Inspect `output/<run_id>/step1_brief.json`
4. Verify:
   - `sections` array has 4-8 items with logical flow
   - `discount_requirements` matches questionnaire input
   - `product_requirements` matches questionnaire input
   - Every section with `image_required: true` has a non-empty `image_description`
   - Every text_slot has realistic `max_chars`
   - `cta_requirements` has at least one primary CTA
