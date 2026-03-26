# PRD 09 — Step 3: Cohesiveness Agent

## Objective

Review ALL outputs from Step 2 agents (structure, discount, products, copy, links) together with the original brief, and ensure everything works as a cohesive whole. Edit any inconsistencies, contradictions, or misalignments. This is the "editor-in-chief" that catches what individual agents missed.

---

## 1. File

`email_gen/pipeline/step3_cohesion.py`

---

## 2. Inputs

| Input | Source |
|-------|--------|
| Step 1 brief | `step1_brief.json` |
| Step 2A structure | `step2a_structure.json` |
| Step 2B discount | `step2b_discount.json` |
| Step 2C products | `step2c_products.json` |
| Step 2D copy | `step2d_copy.json` |
| Step 2E links | `step2e_links.json` |
| Questionnaire | `questionnaire.yaml` |
| Brand identity | `brand/identity_text/` |

All loaded via `io_util.read_json()` and `questionnaire.load()`.

---

## 3. LLM Configuration

- **Model:** `config.cohesion_model()` (default: `gemini-2.5-pro`)
- **System prompt:** `STEP3_SYSTEM`

This agent needs strong reasoning to cross-reference multiple data sources and catch subtle inconsistencies.

---

## 4. System Prompt

```
You are a senior email marketing editor and QA specialist. You review all components of an email campaign (structure, copy, discount, products, links) and ensure they work together cohesively.

Output valid JSON only, no markdown fences.

Schema:
{
  "issues_found": [
    {
      "severity": "<critical|warning|suggestion>",
      "category": "<consistency|accuracy|tone|structure|legal>",
      "description": "<what the issue is>",
      "affected_components": ["<step2a|step2b|step2c|step2d|step2e>"],
      "fix_applied": "<what was changed to fix it>"
    }
  ],
  "revised_copy": {
    "subject_line": "<revised or original if no change>",
    "preheader": "<revised or original>",
    "copy_by_token": { "<same structure as step2d>" },
    "product_copy": { "<same structure as step2d>" },
    "fine_print": "<revised or original>"
  },
  "revised_structure": {
    "html_skeleton": "<revised HTML or null if no structural changes>",
    "token_manifest": "<revised manifest or null if no changes>"
  },
  "revised_links": {
    "links_by_token": { "<revised or original>" }
  },
  "cohesion_score": <1-10>,
  "cohesion_summary": "<2-3 sentences on overall cohesion quality>"
}

Checks to perform (ALL of these):

1. DISCOUNT CONSISTENCY
   - Does the copy reference the correct discount code from step2b?
   - Does the copy state the correct discount value (e.g., "20% off" matches the actual discount)?
   - Are discount conditions mentioned in the fine print?
   - Do links include the discount code parameter?

2. PRODUCT ACCURACY
   - Do product names in the copy match the selected products from step2c?
   - Are product prices accurate?
   - Do product links point to the correct product pages?
   - Does the number of products in the copy match the structure's product slots?

3. CTA ALIGNMENT
   - Does CTA text match the CTA destination (e.g., "Shop Beef Crisps" links to beef crisps collection, not homepage)?
   - Are all CTA links populated and valid?
   - Is there a clear primary CTA that stands out?

4. TONE CONSISTENCY
   - Is the tone consistent across all copy (subject line, headlines, body, CTAs)?
   - Does the tone match the brief's tone_and_voice directive?
   - Does the copy sound like Yay's brand voice (heritage, texture, sensory)?

5. STRUCTURE-COPY MATCH
   - Does every text token in the HTML skeleton have corresponding copy?
   - Does the copy fit within the max_chars constraints?
   - Are there any orphaned tokens (in HTML but no copy, or copy but no HTML token)?

6. LEGAL & COMPLIANCE
   - Is there an unsubscribe link?
   - If there's a discount, are terms/conditions/expiry stated?
   - No misleading claims or promises?

7. FLOW & NARRATIVE
   - Does the email tell a coherent story from top to bottom?
   - Does each section build on the previous one?
   - Is there a clear path from hook → value → action?

Rules:
- For critical issues: MUST fix in the revised outputs
- For warnings: SHOULD fix, explain if not
- For suggestions: note but don't necessarily fix
- If no changes needed for a component, set its revised value to null (not a copy of the original)
- revised_copy should be a COMPLETE copy object (not just the changed fields) — downstream agents need the full thing
- revised_links should be a COMPLETE links object
- revised_structure can be null if no HTML changes needed (most common case)
- cohesion_score: 8-10 = ready to proceed, 5-7 = proceed with noted issues, 1-4 = major problems
```

---

## 5. User Prompt Construction

```python
def _build_prompt(brief, structure, discount, products, copy, links, questionnaire, brand_identity):
    return f"""Review all email campaign components for cohesion and consistency.

ORIGINAL BRIEF:
{json.dumps(brief, indent=2)[:6000]}

QUESTIONNAIRE SUMMARY:
{questionnaire_module.summarize(questionnaire)}

HTML STRUCTURE (token manifest):
{json.dumps(structure.get('token_manifest', []), indent=2)[:4000]}

DISCOUNT DETAILS:
{json.dumps(discount, indent=2)[:2000]}

SELECTED PRODUCTS:
{json.dumps(products.get('featured_products', []), indent=2)[:4000]}

GENERATED COPY:
{json.dumps(copy, indent=2)[:8000]}

GENERATED LINKS:
{json.dumps(links, indent=2)[:3000]}

BRAND IDENTITY:
{brand_identity[:4000]}

Perform ALL cohesion checks per the system instructions. Return the full revised outputs.
"""
```

---

## 6. Function Signature

```python
def run(run_dir: Path) -> Dict[str, Any]:
    """
    Load all step 2 artifacts, call LLM for cohesion review, return revised outputs.
    """
```

---

## 7. Output

Written to `output/<run_id>/step3_cohesion.json`.

### How Downstream Agents Use This

- **Step 4 (Images):** Uses `revised_structure` (if not null) or falls back to original `step2a_structure.json`
- **Step 5 (Assembly):** Uses `revised_copy`, `revised_links`, and `revised_structure` as the authoritative versions. Falls back to original step2 outputs for any null revised fields.

### Fallback Logic (used by steps 4 and 5)

```python
def get_final_copy(run_dir: Path) -> Dict:
    cohesion = io_util.load_step(run_id, io_util.STEP3)
    if cohesion and cohesion.get("revised_copy"):
        return cohesion["revised_copy"]
    return io_util.read_json(run_dir / io_util.STEP2D)

def get_final_structure(run_dir: Path) -> Dict:
    cohesion = io_util.load_step(run_id, io_util.STEP3)
    if cohesion and cohesion.get("revised_structure") and cohesion["revised_structure"].get("html_skeleton"):
        return cohesion["revised_structure"]
    return io_util.read_json(run_dir / io_util.STEP2A)

def get_final_links(run_dir: Path) -> Dict:
    cohesion = io_util.load_step(run_id, io_util.STEP3)
    if cohesion and cohesion.get("revised_links") and cohesion["revised_links"].get("links_by_token"):
        return cohesion["revised_links"]
    return io_util.read_json(run_dir / io_util.STEP2E)
```

These helper functions should live in `io_util.py` or a new `step_utils.py`.

---

## 8. Test Checkpoint

1. Run `python main.py step3 --run <run_id>` (requires all step 2 outputs)
2. Inspect `step3_cohesion.json`:
   - `issues_found` lists any problems detected (should be non-empty for most runs)
   - Critical issues have fixes applied in the revised outputs
   - `revised_copy` is a complete copy object (not partial)
   - `cohesion_score` is reasonable (8+ for a well-generated campaign)
3. Diff `revised_copy` against `step2d_copy.json` to see what changed
4. Intentionally introduce an error (e.g., wrong discount code in copy) and verify the cohesion agent catches and fixes it
