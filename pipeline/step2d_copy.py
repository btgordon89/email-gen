"""Step 2D: Copy Generator — write all email text content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import base_step, config, gemini_text, io_util, questionnaire as questionnaire_module, validators


class Step2dCopy(base_step.BaseStep):
    """Generate all email copy (subject, preheader, body text, CTAs)."""
    
    step_id = "step2d_copy"
    output_filename = io_util.STEP2D
    model_fn = staticmethod(config.copy_model)
    default_schema = {
        "subject_line": "",
        "preheader": "",
        "copy_by_token": {},
        "product_copy": {},
        "fine_print": "",
        "copy_rationale": "",
    }
    
    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load brief, structure, discount, products, questionnaire, brand identity."""
        full_brief = io_util.read_json(run_dir / io_util.STEP1)
        brief = self._brief_for_email(full_brief)
        structure = io_util.read_json(self._step_path(run_dir, io_util.STEP2A))
        discount = io_util.read_json(self._step_path(run_dir, io_util.STEP2B, per_email=False))
        products = io_util.read_json(self._step_path(run_dir, io_util.STEP2C))
        questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")
        
        focus = questionnaire.get("product_focus", "")
        pc = focus if focus not in ("all", "") else None
        brand_identity = gemini_text.load_brand_identity_text(product_category=pc)
        review_highlights = gemini_text.load_review_highlights(
            product_focus=pc, max_chars=5000
        )

        return {
            "brief": brief,
            "structure": structure,
            "discount": discount,
            "products": products,
            "questionnaire": questionnaire,
            "brand_identity": brand_identity,
            "review_highlights": review_highlights,
        }
    
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build copy generation prompt."""
        brief = inputs["brief"]
        structure = inputs["structure"]
        discount = inputs["discount"]
        products = inputs["products"]
        questionnaire = inputs["questionnaire"]
        brand_identity = inputs["brand_identity"]
        
        copy_tokens = [
            t for t in structure.get("token_manifest", [])
            if t.get("source_agent") == "copy"
        ]
        # Slim representation — token name only, no desc/section bloat — avoids truncation
        copy_token_names = [t["token"] for t in copy_tokens]
        copy_tokens_text = "\n".join(copy_token_names)

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

        featured = products.get("featured_products", [])
        products_text = "\n".join([
            f"- {p['title']} ({p['handle']}): {p['price']} — {p.get('short_description', '')}"
            for p in featured
        ])

        discount_text = "No discount for this campaign."
        if discount.get("discount_code"):
            discount_text = (
                f"Code: {discount['discount_code']}\n"
                f"Display: {discount['display_text']}\n"
                f"Conditions: {discount.get('conditions_summary', 'None')}"
            )
        else:
            discount_text += "\n\nNote: Fine print must still include company info, unsubscribe language, and legal compliance text."

        review_highlights = inputs["review_highlights"]
        review_section = ""
        if review_highlights:
            review_section = f"""
CUSTOMER QUOTES (verbatim — use these EXACTLY when filling social_proof tokens; attribute as "— FirstName"):
{review_highlights}
"""
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
{text_slots_text[:6000]}

COPY TOKENS TO FILL (you MUST provide a value for every single token listed here):
{copy_tokens_text}

DISCOUNT DETAILS:
{discount_text}

FEATURED PRODUCTS:
{products_text}

BRAND IDENTITY:
{brand_identity[:8000]}
{review_section}
QUESTIONNAIRE CONTEXT:
- Theme: {questionnaire.get('email_theme', '')}
- Key message: {questionnaire.get('key_message', '')}
- Seasonal hook: {questionnaire.get('seasonal_hook', '')}

Generate all copy per the system schema. Every copy token must be filled."""
    
    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """Validate that all required copy tokens are filled."""
        return validators.validate_copy_completeness(output, inputs["structure"])

    def run(self, run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
        output = super().run(run_dir, email_num=email_num, total_emails=total_emails)
        # Ensure {{email_subject}} and {{preheader_text}} are always in copy_by_token.
        # The LLM writes these as top-level fields (subject_line / preheader) but sometimes
        # omits them from copy_by_token; sync them here before the output file is finalised.
        copy_by_token = output.setdefault("copy_by_token", {})
        patched = False
        if "{{email_subject}}" not in copy_by_token and output.get("subject_line"):
            copy_by_token["{{email_subject}}"] = output["subject_line"]
            patched = True
        if "{{preheader_text}}" not in copy_by_token and output.get("preheader"):
            copy_by_token["{{preheader_text}}"] = output["preheader"]
            patched = True
        if patched:
            io_util.write_json(
                run_dir / io_util.step_filename(self.output_filename, email_num, total_emails),
                output,
            )
        return output


# Singleton instance for backward compatibility
_instance = Step2dCopy()


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Generate all email copy."""
    return _instance.run(run_dir, email_num=email_num, total_emails=total_emails)
