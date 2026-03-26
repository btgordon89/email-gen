# Email Gen v1

An AI-powered email marketing pipeline that turns a short campaign questionnaire into complete, production-ready HTML emails — copy, product selection, images, and all.

Built for Shopify + Klaviyo stores. Uses Google Gemini for text and image generation, with optional Anthropic Claude for copywriting.

---

## What it does

Fill out a YAML questionnaire describing your campaign (goal, tone, discount, products), then run the pipeline. It will:

- Pull live product data from your Shopify store
- Generate a creative brief and campaign strategy
- Write email copy (subject line, headlines, body, CTAs)
- Generate on-brand product images via Gemini
- Assemble a final HTML email ready to drop into Klaviyo
- Optionally generate a coordinated **multi-email sequence** from one brief

Every step produces auditable JSON output so you can inspect or replay any part of the pipeline.

---

## Pipeline overview

```
questionnaire.yaml
       │
  Step 1: Brief         ← campaign strategy & creative direction
       │
  ┌────┼────┐
  │    │    │
 2A   2B   2C           ← HTML structure / discount code / product selection
  │    │    │
  └────┼────┘
      2D  2E  2F        ← copy generation / CTA links / link validation
       │
  Step 3: Cohesion      ← cross-email consistency review (sequences)
       │
  Step 4: Images        ← Gemini image generation
       │
  Step 5: Assembly      ← render final HTML email
       │
  Step 6: Template      ← upload images to Klaviyo CDN
       │
  Step 7: Review + Patch ← final QA pass
       │
  output/<run>/email_1.html  (+ email_2.html, ... for sequences)
```

---

## Requirements

- Python 3.10+
- Google Gemini API key (text + image generation)
- Shopify Admin API credentials
- Klaviyo API key

---

## Setup

```bash
git clone https://github.com/your-username/email-gen-v1.git
cd email-gen-v1

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

### Brand assets

The pipeline reads brand context from a `brand/` directory at the repo root (sibling to `email_gen_v1/`):

```
your-repo/
├── email_gen/          ← this project
└── brand/
    ├── identity_text/  ← brand voice, product category descriptions
    ├── assets/         ← logos, product images, bag images
    └── customer_reviews/
        └── review_highlights.txt
```

See `pipeline/config.py` for the exact expected paths. The pipeline degrades gracefully if brand files are missing — it just won't have that context.

---

## Usage

### 1. Create a questionnaire

```bash
python main.py new-questionnaire --output my_campaign.yaml
# Edit my_campaign.yaml with your campaign details
```

Or copy `questionnaire_template.yaml` directly and fill it in. See `fixtures/valid_questionnaire.yaml` for a working example.

### 2. Initialize a run

```bash
python main.py init-run --name summer_sale --questionnaire my_campaign.yaml
# → output/summer_sale/
```

### 3. Run the pipeline step by step

```bash
python main.py step1  --run summer_sale
python main.py step2b --run summer_sale                          # discount (shared)
python main.py step2a --run summer_sale --email-num 1 --total-emails 1
python main.py step2c --run summer_sale --email-num 1 --total-emails 1
python main.py step2d --run summer_sale --email-num 1 --total-emails 1
python main.py step2e --run summer_sale --email-num 1 --total-emails 1
python main.py step2f --run summer_sale --email-num 1 --total-emails 1
python main.py step3  --run summer_sale --email-num 1 --total-emails 1
python main.py step4  --run summer_sale --email-num 1 --total-emails 1
python main.py step5  --run summer_sale --email-num 1 --total-emails 1
python main.py step6  --run summer_sale --email-num 1 --total-emails 1
python main.py step7  --run summer_sale --email-num 1 --total-emails 1
```

For a 3-email sequence, set `sequence_num_emails: 3` in the questionnaire and repeat steps 2A–7 for `--email-num 1`, `2`, `3`.

### 4. Other commands

```bash
# Generate campaign ideas from customer reviews
python main.py ideas --product-focus beef_crisps

# Analyse brand screenshots for visual identity
python main.py brand-analysis --inspo-dir ./brand/website
```

---

## Output structure

Each run produces:

```
output/summer_sale/
├── questionnaire.yaml      ← copy of your input
├── step1_brief.json
├── step2a_structure.json
├── step2b_discount.json
├── step2c_products.json
├── step2d_copy.json
├── step2e_links.json
├── step3_cohesion.json
├── audit/
│   ├── step1_brief.audit.json
│   └── ...                 ← full prompt/response audit trail per step
├── images/
│   └── ...                 ← generated images
└── email_1.html            ← final deliverable
```

---

## Model configuration

Default models (all Gemini):

| Step | Default model |
|------|--------------|
| Brief, Copy, Cohesion, Assembly, Review | `gemini-2.5-pro` |
| Structure, Discount, Products, Links | `gemini-2.5-flash` |
| Images | `gemini-3-pro-image-preview` |

Override per-step in `.env` (e.g. `EMAIL_COPY_MODEL=gemini-2.5-flash`) or edit `pipeline/models_config.yaml` for a persistent config. See `.env.example` for all available overrides.

---

## Documentation

Full architecture docs and PRDs are in [`docs/`](docs/):

- [`docs/prds/PRD_00_OVERVIEW.md`](docs/prds/PRD_00_OVERVIEW.md) — pipeline architecture
- [`docs/refactoring/ARCHITECTURE_DIAGRAM.md`](docs/refactoring/ARCHITECTURE_DIAGRAM.md) — visual architecture diagram
- [`docs/refactoring/REFACTORING_COMPLETE.md`](docs/refactoring/REFACTORING_COMPLETE.md) — recent improvements

---

## License

MIT
