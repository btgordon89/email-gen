# PRD 04 — Step 2A: Structure Refiner Agent

## Objective

Take the email brief from Step 1 and produce a detailed HTML skeleton for the email. The skeleton uses placeholder tokens (e.g., `{{hero_headline}}`, `{{hero_image}}`) that will be filled in by later agents. This agent is the "email architect."

---

## 1. File

`email_gen/pipeline/step2a_structure.py`

---

## 2. Inputs

| Input | Source | How Loaded |
|-------|--------|------------|
| Step 1 brief | `output/<run_id>/step1_brief.json` | `io_util.read_json()` |
| Base components | `email_gen/email_templates/base_components.html` | Read as string |

---

## 3. LLM Configuration

- **Model:** `config.structure_model()` (default: `gemini-2.5-flash`)
- **System prompt:** `STEP2A_SYSTEM` constant

---

## 4. Base Components File

`email_gen/email_templates/base_components.html` — a reference file containing reusable HTML patterns for email. NOT a full template — just building blocks the LLM can reference.

```html
<!-- EMAIL BASE COMPONENTS REFERENCE
     The Structure Agent should use these patterns as building blocks.
     All CSS must be inline (email client compatibility).
-->

<!-- DOCUMENT WRAPPER -->
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>{{email_subject}}</title>
  <!--[if mso]><style>body{font-family:Arial,sans-serif!important;}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;">

<!-- CENTERED CONTAINER (600px max) -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
<tr><td align="center" style="padding:20px 10px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;">

<!-- === SECTION: HEADER === -->
<tr><td style="background-color:#2c5f7f;padding:24px 30px;text-align:center;">
  {{header_content}}
</td></tr>

<!-- === SECTION: HERO BANNER === -->
<tr><td style="padding:0;">
  <img src="{{hero_image}}" alt="{{hero_image_alt}}" width="600" style="display:block;width:100%;height:auto;">
</td></tr>

<!-- === SECTION: TEXT BLOCK === -->
<tr><td style="padding:30px 40px;">
  <h1 style="font-family:'Bebas Neue',Impact,sans-serif;font-size:32px;color:#2c5f7f;margin:0 0 12px;">{{headline}}</h1>
  <p style="font-family:'Outfit',Arial,sans-serif;font-size:16px;line-height:1.6;color:#333333;margin:0 0 20px;">{{body_copy}}</p>
</td></tr>

<!-- === SECTION: CTA BUTTON === -->
<tr><td style="padding:0 40px 30px;text-align:center;">
  <a href="{{cta_link}}" style="display:inline-block;background-color:#D32F2F;color:#ffffff;font-family:'Bebas Neue',Impact,sans-serif;font-size:20px;padding:14px 40px;text-decoration:none;border-radius:6px;">{{cta_text}}</a>
</td></tr>

<!-- === SECTION: PRODUCT GRID (3-col) === -->
<tr><td style="padding:20px 20px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
  <tr>
    <td width="33%" style="padding:10px;text-align:center;vertical-align:top;">
      <img src="{{product_1_image}}" alt="{{product_1_name}}" width="160" style="display:block;margin:0 auto 10px;width:160px;height:auto;">
      <p style="font-family:'Outfit',Arial,sans-serif;font-size:14px;font-weight:600;color:#2c5f7f;margin:0 0 4px;">{{product_1_name}}</p>
      <p style="font-family:'Outfit',Arial,sans-serif;font-size:14px;color:#666;margin:0 0 10px;">{{product_1_price}}</p>
      <a href="{{product_1_link}}" style="font-family:'Outfit',Arial,sans-serif;font-size:13px;color:#D32F2F;text-decoration:underline;">Shop Now</a>
    </td>
    <td width="33%" style="padding:10px;text-align:center;vertical-align:top;">
      <!-- product_2 same pattern -->
    </td>
    <td width="33%" style="padding:10px;text-align:center;vertical-align:top;">
      <!-- product_3 same pattern -->
    </td>
  </tr>
  </table>
</td></tr>

<!-- === SECTION: BENEFITS LIST === -->
<tr><td style="padding:30px 40px;background-color:#FFF8E1;">
  <h2 style="font-family:'Bebas Neue',Impact,sans-serif;font-size:24px;color:#2c5f7f;margin:0 0 16px;">{{benefits_heading}}</h2>
  <ul style="font-family:'Outfit',Arial,sans-serif;font-size:15px;color:#333;padding-left:20px;margin:0;">
    {{benefits_bullets}}
  </ul>
</td></tr>

<!-- === SECTION: FOOTER === -->
<tr><td style="background-color:#2c5f7f;padding:24px 30px;text-align:center;">
  <p style="font-family:'Outfit',Arial,sans-serif;font-size:12px;color:#ffffff;margin:0 0 8px;">{{footer_tagline}}</p>
  <p style="font-family:'Outfit',Arial,sans-serif;font-size:11px;color:#aaccdd;margin:0;">
    <a href="{{unsubscribe_link}}" style="color:#aaccdd;text-decoration:underline;">Unsubscribe</a> |
    <a href="{{preferences_link}}" style="color:#aaccdd;text-decoration:underline;">Email Preferences</a>
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
```

---

## 5. System Prompt

```
You are an expert email HTML developer specializing in Klaviyo-compatible, mobile-responsive promotional emails.

You will receive an email brief with sections, and a reference file of HTML building blocks. Your job is to produce a COMPLETE HTML email skeleton using placeholder tokens.

Output valid JSON only, no markdown fences.

Schema:
{
  "html_skeleton": "<complete HTML string with {{token}} placeholders>",
  "token_manifest": [
    {
      "token": "{{hero_headline}}",
      "source_agent": "<copy|image|link|discount|static>",
      "description": "<what this token should be replaced with>",
      "section_id": "<which section this token belongs to>"
    }
  ],
  "responsive_notes": "<brief notes on how the email adapts to mobile>",
  "design_decisions": "<brief notes on layout choices made>"
}

Rules:
- ALL CSS must be inline (no <style> blocks except for media queries in <head>)
- Use table-based layout for email client compatibility
- Max width: 600px, centered
- Brand fonts: 'Bebas Neue' for headlines/CTAs, 'Outfit' for body text, with safe fallbacks (Impact, Arial)
- Brand colors: Navy #2c5f7f, Gold #FFB800/#FFA000, Red #D32F2F, White #ffffff, Light warm #FFF8E1
- Include MSO conditionals for Outlook: <!--[if mso]> ... <![endif]-->
- Include responsive media queries in <head> for max-width:600px breakpoint
- Image tokens use format: {{section_id_image}} (e.g., {{hero_image}})
- Text tokens use format: {{slot_id}} matching the brief's text_slots (e.g., {{hero_headline}})
- Link tokens use format: {{cta_id_link}} (e.g., {{hero_cta_link}})
- Product tokens: {{product_N_image}}, {{product_N_name}}, {{product_N_price}}, {{product_N_link}}
- Discount code token: {{discount_code}}
- Always include: unsubscribe link ({{unsubscribe_link}}), email preferences ({{preferences_link}})
- The token_manifest must list EVERY token used in the HTML
- source_agent indicates which downstream agent provides the value:
  - "copy" = Step 2D copy agent
  - "image" = Step 4 image agent
  - "link" = Step 2E link agent
  - "discount" = Step 2B discount agent
  - "static" = hardcoded brand values (logo URL, brand name, etc.)
- The HTML must be production-ready structure — not a wireframe
```

---

## 6. User Prompt Construction

```python
def _build_prompt(brief: Dict[str, Any], base_components: str) -> str:
    sections_json = json.dumps(brief.get("sections", []), indent=2)
    cta_json = json.dumps(brief.get("cta_requirements", []), indent=2)
    discount_json = json.dumps(brief.get("discount_requirements", {}), indent=2)
    product_json = json.dumps(brief.get("product_requirements", {}), indent=2)

    return f"""Build the HTML email skeleton for this campaign.

CREATIVE CONCEPT:
{brief.get('creative_concept', '')}

SECTIONS (from the brief — build HTML for each):
{sections_json}

CTA REQUIREMENTS:
{cta_json}

DISCOUNT REQUIREMENTS:
{discount_json}

PRODUCT REQUIREMENTS:
{product_json}

TONE & VOICE:
{brief.get('tone_and_voice', '')}

REFERENCE HTML COMPONENTS (use these patterns as building blocks):
{base_components[:8000]}

Generate the complete HTML skeleton with all placeholder tokens per the system schema.
"""
```

---

## 7. Function Signature

```python
def run(run_dir: Path) -> Dict[str, Any]:
    """
    Load step1 brief, load base components, call LLM, return structure dict.
    Output includes html_skeleton (string) and token_manifest (list).
    """
```

---

## 8. Output

Written to `output/<run_id>/step2a_structure.json`.

The `token_manifest` is critical — it's the contract between the structure agent and all downstream agents. Each token must be accounted for and assigned to a source agent.

---

## 9. Test Checkpoint

1. Run `python main.py step2a --run <run_id>` (requires step1 to have run)
2. Inspect `step2a_structure.json`:
   - `html_skeleton` is valid HTML (paste into browser, should render a skeleton with `{{tokens}}` visible)
   - `token_manifest` lists every `{{token}}` that appears in the HTML
   - Every token has a `source_agent` assignment
   - HTML uses inline CSS, table layout, 600px max-width
   - Responsive media queries present in `<head>`
   - Brand colors and fonts are used correctly
