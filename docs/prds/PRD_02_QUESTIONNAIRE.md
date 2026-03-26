# PRD 02 — Questionnaire System

## Objective

Provide a structured YAML questionnaire that the user fills out before running the pipeline. This replaces a freeform `--brief` flag and ensures the agentic system has comprehensive, unambiguous input.

---

## 1. Questionnaire Template

File: `email_gen/questionnaire_template.yaml`

```yaml
# ============================================================================
# Yay's Email Generator — Campaign Questionnaire
# Fill out each field below. Leave blank or remove optional fields if not needed.
# ============================================================================

# --- CAMPAIGN BASICS ---

# What is this email about? Be descriptive.
# Examples: "Summer BBQ sale", "New Crispy Beef Bits launch", "Flash sale clearance"
email_theme: ""

# What is the single most important goal of this email?
# Options: "drive_sales", "clear_inventory", "introduce_new_product", "re_engage", "announce_promotion"
primary_goal: ""

# Who is this email targeting?
# Options: "all_subscribers", "new_subscribers", "existing_customers", "lapsed_buyers", "vip_customers"
target_audience: ""

# --- TONE & MESSAGING ---

# What tone should the email convey?
# Options: "urgent_fomo", "warm_inviting", "bold_energetic", "playful_fun", "premium_elevated"
tone: ""

# The ONE thing the reader should take away from this email.
# Example: "Yay's now has bite-sized beef bits you can sprinkle on anything"
key_message: ""

# Any seasonal or cultural hook to tie into?
# Examples: "Summer BBQ season", "Holiday gifting", "New Year health goals", "Asian Heritage Month"
# Leave blank if none.
seasonal_hook: ""

# How urgent should this feel?
# Examples: "48_hour_flash_sale", "limited_stock", "ends_this_weekend", "no_urgency"
urgency: ""

# --- DISCOUNT & PROMOTION ---

# Type of discount to offer.
# Options: "percentage", "fixed_amount", "bogo", "free_shipping", "bundle_deal", "none"
discount_type: ""

# The discount value or description.
# Examples: "20%", "$5 off", "Buy 2 get 1 free", "Free shipping on orders $50+"
discount_value: ""

# Any conditions on the discount?
# Examples: "First order only", "Minimum $30 order", "Beef crisps only", "No restrictions"
discount_conditions: ""

# Should a unique discount code be generated? (true/false)
# If true, Agent 2B will create a real discount code in Shopify.
generate_discount_code: true

# --- PRODUCTS ---

# Which product category to focus on.
# Options: "beef_crisps", "pork_crisps", "crispy_beef_bits", "variety_packs", "all"
product_focus: ""

# How many products should be featured in the email? (1-6)
num_featured_products: 3

# Specific products to feature (optional). Use product titles or SKUs.
# Leave empty to let the Product Selector agent choose.
# Examples:
#   - "Spicy Yay's Beef Crisps"
#   - "SKU:YOS3"
#   - "NEW! Crispy Beef Bits Sampler"
featured_products: []

# What criteria should guide product selection if not manually specified?
# Options: "best_sellers", "newest", "highest_margin", "seasonal_fit", "variety_across_flavors"
selection_criteria: "best_sellers"

# --- CALL TO ACTION ---

# Where should the primary CTA link to?
# Options: "homepage", "collection_page", "specific_product", "custom_url"
cta_destination: ""

# If cta_destination is "specific_product", which product?
# Example: "Spicy Yay's Beef Crisps"
cta_specific_product: ""

# If cta_destination is "custom_url", what URL?
cta_custom_url: ""

# --- ADDITIONAL CONTEXT ---

# Anything else the agents should know? Free text.
# Examples: "We just got featured on TikTok", "Competitor ran a similar sale last week",
#           "This is a follow-up to last week's teaser email"
additional_notes: ""
```

---

## 2. pipeline/questionnaire.py

### Functions

#### `create_template(output_path: Path) -> Path`
Copies `questionnaire_template.yaml` to the specified path. Returns the path.

#### `load(path: Path) -> Dict[str, Any]`
Loads and validates a filled-out questionnaire YAML file. Returns a typed dict.

**Validation rules:**
- `email_theme` — required, non-empty string
- `primary_goal` — required, must be one of the allowed values
- `target_audience` — required, must be one of the allowed values
- `tone` — required, must be one of the allowed values
- `key_message` — required, non-empty string
- `discount_type` — required, must be one of the allowed values
- `discount_value` — required if `discount_type` is not `"none"`
- `product_focus` — required, must be one of the allowed values
- `num_featured_products` — integer 1-6, defaults to 3
- `cta_destination` — required, must be one of the allowed values
- `cta_specific_product` — required if `cta_destination` is `"specific_product"`
- `cta_custom_url` — required if `cta_destination` is `"custom_url"`
- All other fields are optional (can be empty string or omitted)

**On validation failure:** Raise `ValueError` with a clear message listing all invalid fields and what's expected.

#### `summarize(questionnaire: Dict[str, Any]) -> str`
Returns a human-readable text summary of the questionnaire (used as context in LLM prompts). Format:

```
CAMPAIGN QUESTIONNAIRE SUMMARY
==============================
Theme: Summer BBQ sale
Goal: drive_sales
Audience: all_subscribers
Tone: bold_energetic
Key Message: Yay's crispy beef crisps are the perfect BBQ companion
Seasonal Hook: Summer BBQ season
Urgency: ends_this_weekend
Discount: 20% percentage (First order only) [code will be auto-generated]
Product Focus: beef_crisps (3 featured, selected by: best_sellers)
CTA Destination: collection_page
Additional Notes: We just got featured on TikTok
```

---

## 3. CLI Integration

In `main.py`:

```
python main.py new-questionnaire [--output path/to/questionnaire.yaml]
```

Default output: current directory `./questionnaire.yaml`.

The `init-run` command accepts `--questionnaire path/to/filled.yaml`:

```
python main.py init-run --name summer_sale --questionnaire ./questionnaire.yaml
```

This copies the questionnaire into the run directory and stores the path in `meta.json`.

---

## 4. Allowed Values Reference

### primary_goal
`drive_sales`, `clear_inventory`, `introduce_new_product`, `re_engage`, `announce_promotion`

### target_audience
`all_subscribers`, `new_subscribers`, `existing_customers`, `lapsed_buyers`, `vip_customers`

### tone
`urgent_fomo`, `warm_inviting`, `bold_energetic`, `playful_fun`, `premium_elevated`

### discount_type
`percentage`, `fixed_amount`, `bogo`, `free_shipping`, `bundle_deal`, `none`

### urgency
`48_hour_flash_sale`, `limited_stock`, `ends_this_weekend`, `no_urgency`, or any free-text string

### product_focus
`beef_crisps`, `pork_crisps`, `crispy_beef_bits`, `variety_packs`, `all`

### selection_criteria
`best_sellers`, `newest`, `highest_margin`, `seasonal_fit`, `variety_across_flavors`

### cta_destination
`homepage`, `collection_page`, `specific_product`, `custom_url`

---

## 5. Test Checkpoint

1. `python main.py new-questionnaire` creates a valid YAML file
2. Fill it out with test data and run `python -c "from pipeline.questionnaire import load; print(load(Path('questionnaire.yaml')))"`
3. Verify validation catches missing required fields
4. `python main.py init-run --name test --questionnaire questionnaire.yaml` copies the file into the run dir
