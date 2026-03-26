# Email Generator v1 — Master PRD Overview

## Project Summary

Build a multi-agent email generation system for Yay's Beef Crisps that takes structured user input (a questionnaire) and produces a fully assembled, mobile-and-desktop-friendly HTML promotional email ready for Klaviyo upload. The system lives at `email_gen/` inside the `static_ads_gen` monorepo.

## Architecture

```
User fills out questionnaire.yaml
        │
        ▼
┌─────────────────────────────┐
│  Step 1: Brief Generator    │  Takes questionnaire + brand identity → structured email brief
└──────────────┬──────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐   ◄── Wave 1 (parallel)
│Step 2A │ │Step 2B │ │Step 2C │
│Structure│ │Discount│ │Products│
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    │     ┌────┴──────────┘
    │     ▼
    │  ┌────────┐ ┌────────┐        ◄── Wave 2 (depends on 2B + 2C)
    │  │Step 2D │ │Step 2E │
    │  │  Copy  │ │ Links  │
    │  └───┬────┘ └───┬────┘
    │      │          │
    └──────┼──────────┘
           ▼
┌─────────────────────────────┐
│  Step 3: Cohesiveness Agent │  Reviews all Step 2 outputs for consistency
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Step 4: Image Generation   │  Loops per image slot in the structure
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Step 5: HTML Assembly      │  Produces final email_final.html
└─────────────────────────────┘
```

## Key Design Decisions

1. **Stepwise CLI** — Same pattern as `ads_gen_v2`: each step is a standalone CLI command AND can be chained via a `pipeline` command. Each step reads prior artifacts from the run directory and writes its own JSON artifact.

2. **Shared brand files** — Brand identity text and brand assets move to a shared `brand/` directory at the repo root. Both `ads_gen_v2` and `email_gen` reference the same files. `ads_gen_v2` config gets updated with backward-compatible fallback.

3. **Configurable LLM models per agent** — Each step specifies a default model in `config.py` but can be overridden via env vars. Some agents need `gemini-2.5-pro` (brief, copy, cohesion, assembly), others work fine with `gemini-2.5-flash` (structure, discount, products, links).

4. **Shopify Admin API for discounts** — Agent 2B creates real discount codes in Shopify using the existing credentials in `.env`. Agent 2E pulls live product URLs from Shopify.

5. **Image generation via Nano Banana** — Same `gemini-3-pro-image-preview` model and `google-genai` SDK pattern as `ads_gen_v2`.

6. **CDN image URLs** — Final HTML references images via CDN URLs (placeholder format during generation; user uploads to CDN before sending).

7. **Promotional emails only** — Scope is promotional/sale emails for now. Welcome, re-engagement, etc. are future scope.

## File Structure

```
static_ads_gen/
├── .env                              # Existing: GOOGLE_API_KEY, SHOPIFY_* credentials
├── brand/                            # NEW: shared brand files (moved from ads_gen_v2)
│   ├── identity_text/
│   │   ├── key_brand_attributes.txt
│   │   └── product_categories/
│   │       ├── beef_crisps/positioning.txt
│   │       ├── pork_crisps/positioning.txt
│   │       └── crispy_beef_bits/positioning.txt
│   └── assets/
│       ├── brand_logo/
│       ├── product_images/<category>/<flavor>/
│       ├── bag_images/<category>/<flavor>/
│       └── flavor_identity/<category>/<flavor>/
├── ads_gen_v2/                       # Existing (config updated to use brand/)
│   └── pipeline/config.py            # Updated: brand_identity_dir() → ../../brand/identity_text
├── email_gen/                     # NEW
│   ├── main.py                       # CLI entry point
│   ├── .env.example
│   ├── requirements.txt
│   ├── questionnaire_template.yaml   # Template for user input
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── gemini_text.py
│   │   ├── gemini_image.py
│   │   ├── shopify_client.py
│   │   ├── io_util.py
│   │   ├── questionnaire.py
│   │   ├── step1_brief.py
│   │   ├── step2a_structure.py
│   │   ├── step2b_discount.py
│   │   ├── step2c_products.py
│   │   ├── step2d_copy.py
│   │   ├── step2e_links.py
│   │   ├── step3_cohesion.py
│   │   ├── step4_images.py
│   │   └── step5_assembly.py
│   ├── email_templates/
│   │   └── base_components.html
│   └── output/<run_id>/
│       ├── meta.json
│       ├── questionnaire.yaml
│       ├── step1_brief.json
│       ├── step2a_structure.json
│       ├── step2b_discount.json
│       ├── step2c_products.json
│       ├── step2d_copy.json
│       ├── step2e_links.json
│       ├── step3_cohesion.json
│       ├── step4_images.json
│       ├── images/
│       │   ├── hero.png
│       │   └── ...
│       ├── email_final.html
│       └── email_preview.html
```

## Environment Variables

All loaded from `email_gen/.env` with fallback to repo root `.env`:

| Variable | Source | Used By |
|----------|--------|---------|
| `GOOGLE_API_KEY` | Root `.env` | All Gemini calls (text + image) |
| `SHOPIFY_SHOP_URL` | Root `.env` | Steps 2B, 2C, 2E |
| `SHOPIFY_ADMIN_API_TOKEN` | Root `.env` | Steps 2B, 2C, 2E |
| `EMAIL_BRIEF_MODEL` | `email_gen/.env` | Step 1 (default: `gemini-2.5-pro`) |
| `EMAIL_STRUCTURE_MODEL` | `email_gen/.env` | Step 2A (default: `gemini-2.5-flash`) |
| `EMAIL_DISCOUNT_MODEL` | `email_gen/.env` | Step 2B (default: `gemini-2.5-flash`) |
| `EMAIL_PRODUCTS_MODEL` | `email_gen/.env` | Step 2C (default: `gemini-2.5-flash`) |
| `EMAIL_COPY_MODEL` | `email_gen/.env` | Step 2D (default: `gemini-2.5-pro`) |
| `EMAIL_LINKS_MODEL` | `email_gen/.env` | Step 2E (default: `gemini-2.5-flash`) |
| `EMAIL_COHESION_MODEL` | `email_gen/.env` | Step 3 (default: `gemini-2.5-pro`) |
| `EMAIL_IMAGE_MODEL` | `email_gen/.env` | Step 4 (default: `gemini-3-pro-image-preview`) |
| `EMAIL_ASSEMBLY_MODEL` | `email_gen/.env` | Step 5 (default: `gemini-2.5-pro`) |

## CLI Commands

```bash
# Scaffold
python main.py new-questionnaire                    # Writes a fresh questionnaire_template.yaml
python main.py init-run [--name my_campaign]         # Creates output/<run_id>/ with meta.json

# Individual steps
python main.py step1 --run RUN                       # Brief generator
python main.py step2a --run RUN                      # Structure refiner
python main.py step2b --run RUN                      # Discount strategy
python main.py step2c --run RUN                      # Product selector
python main.py step2d --run RUN                      # Copy generator
python main.py step2e --run RUN                      # Link agent
python main.py step3 --run RUN                       # Cohesiveness review
python main.py step4 --run RUN                       # Image generation
python main.py step5 --run RUN                       # HTML assembly

# Full pipeline
python main.py pipeline [--name my_campaign]         # Runs all steps sequentially
```

## Dependencies

```
google-genai>=1.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
requests>=2.31.0
PyYAML>=6.0
```

## Implementation Order

| Phase | Steps | Test Checkpoint |
|-------|-------|-----------------|
| 0 | Scaffolding: dirs, config, io_util, main.py shell, shared brand move | `python main.py init-run` works; `ads_gen_v2` still works |
| 1 | Questionnaire system | `python main.py new-questionnaire` creates valid template |
| 2 | gemini_text.py + shopify_client.py | Unit test: text gen + Shopify product fetch |
| 3 | Step 1: Brief generator | Run step1, inspect JSON brief |
| 4 | Step 2A: Structure refiner | Run step2a, inspect HTML skeleton |
| 5 | Step 2B: Discount strategy | Run step2b, verify Shopify discount created |
| 6 | Step 2C: Product selector | Run step2c, verify product data |
| 7 | Step 2D: Copy generator | Run step2d, inspect copy quality |
| 8 | Step 2E: Link agent | Run step2e, verify URLs with discount params |
| 9 | Step 3: Cohesiveness | Run step3, diff against step2 outputs |
| 10 | Step 4: Image generation | Run step4, visually inspect images |
| 11 | Step 5: HTML assembly | Run step5, open in browser |
| 12 | Full pipeline command | End-to-end run |

## Companion PRD Documents

Each agent/component has its own detailed PRD:

- `PRD_01_SCAFFOLDING.md` — Project setup, config, io_util, shared brand migration
- `PRD_02_QUESTIONNAIRE.md` — User input questionnaire system
- `PRD_03_STEP1_BRIEF.md` — Agent 1: Concept/brief generator
- `PRD_04_STEP2A_STRUCTURE.md` — Agent 2A: Structure refiner
- `PRD_05_STEP2B_DISCOUNT.md` — Agent 2B: Discount strategy + Shopify creation
- `PRD_06_STEP2C_PRODUCTS.md` — Agent 2C: Product selector
- `PRD_07_STEP2D_COPY.md` — Agent 2D: Copy generator
- `PRD_08_STEP2E_LINKS.md` — Agent 2E: Link agent
- `PRD_09_STEP3_COHESION.md` — Agent 3: Cohesiveness review
- `PRD_10_STEP4_IMAGES.md` — Agent 4: Image generation
- `PRD_11_STEP5_ASSEMBLY.md` — Agent 5: HTML assembly
- `PRD_12_MAIN_CLI.md` — CLI entry point and pipeline orchestration
