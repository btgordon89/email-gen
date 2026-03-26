"""Step 1: Brief Generator — master creative brief for the email campaign."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from . import base_step, config, gemini_text, io_util, questionnaire


class Step1Brief(base_step.BaseStep):
    """Generate email campaign brief from questionnaire."""

    step_id = "step1_brief"
    output_filename = io_util.STEP1
    model_fn = staticmethod(config.brief_model)
    default_schema = {
        "creative_concept": "",
        "email_subject_line_direction": "",
        "preheader_direction": "",
        "sections": [],
        "discount_requirements": {},
        "product_requirements": {},
        "cta_requirements": [],
        "tone_and_voice": "",
        "urgency_treatment": "",
        # Sequence mode fields (populated only when sequence_num_emails > 1)
        "sequence_narrative_arc": "",
        "emails": [],
    }

    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load questionnaire and brand identity."""
        q_path = run_dir / "questionnaire.yaml"
        if not q_path.is_file():
            raise FileNotFoundError(f"Questionnaire not found: {q_path}")

        q = questionnaire.load(q_path)

        focus = q.get("product_focus", "").strip()
        product_category = None
        if focus and focus in {"beef_crisps", "pork_crisps", "crispy_beef_bits"}:
            product_category = focus

        brand_identity = gemini_text.load_brand_identity_text(product_category=product_category)
        review_highlights = gemini_text.load_review_highlights(
            product_focus=product_category, max_chars=3000
        )

        return {
            "questionnaire": q,
            "brand_identity": brand_identity,
            "product_category": product_category,
            "review_highlights": review_highlights,
        }

    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build brief generation prompt."""
        q = inputs["questionnaire"]
        brand_identity = inputs["brand_identity"]
        review_highlights = inputs["review_highlights"]

        summary = questionnaire.summarize(q)

        review_section = ""
        if review_highlights:
            review_section = f"""
CUSTOMER QUOTES (verbatim, from real buyers — use these to plan social proof sections):
{review_highlights}
"""

        seq_n = q.get("sequence_num_emails", 1)

        if seq_n > 1:
            # Build per-email override block from questionnaire
            seq_emails = q.get("sequence_emails", [])
            email_overrides = ""
            if seq_emails:
                lines = []
                for e in seq_emails:
                    parts = [f"Email {e['email_num']} (send day {e.get('send_day', 0)})"]
                    if e.get("product_focus"):
                        parts.append(f"product_focus: {e['product_focus']}")
                    if e.get("angle"):
                        parts.append(f"angle: {e['angle']}")
                    if e.get("featured_products"):
                        parts.append(f"pinned products: {', '.join(e['featured_products'])}")
                    lines.append(" | ".join(parts))
                email_overrides = "\n".join(lines)
            else:
                email_overrides = f"(no overrides — auto-generate {seq_n} distinct angles)"

            return f"""Create a {seq_n}-email sequence brief for this campaign.

CAMPAIGN QUESTIONNAIRE:
{summary}

BRAND IDENTITY:
{brand_identity[:12000]}
{review_section}
PER-EMAIL OVERRIDES FROM QUESTIONNAIRE:
{email_overrides}

Generate the sequence brief JSON per the system schema (sequence mode).
The output MUST have a top-level "sequence_narrative_arc" string and an "emails" array with exactly {seq_n} entries.
Each entry in "emails" must follow the full per-email brief schema.
Ensure:
1. sequence_narrative_arc describes the overarching story arc and how the emails escalate
2. Each email has a distinct angle, creative_concept, and product_requirements that differ from the others
3. Product selection criteria must vary across emails to ensure product variety
4. Urgency and tone may escalate across the sequence (e.g. warm → urgent)
5. All text slot guidance is specific enough for a copywriter to execute without ambiguity
6. Image descriptions are detailed enough for an AI image generator"""

        # Single email (original behaviour)
        return f"""Create a detailed email campaign brief based on this questionnaire and brand identity.

CAMPAIGN QUESTIONNAIRE:
{summary}

BRAND IDENTITY:
{brand_identity[:12000]}
{review_section}
Generate the brief JSON per the system schema. Make sure:
1. The creative_concept ties everything together with a clear, compelling angle
2. Sections flow logically (hook → value → proof → action)
3. Discount and product requirements faithfully reflect the questionnaire
4. Text slot guidance is specific enough for a copywriter to execute without ambiguity
5. Image descriptions are detailed enough for an AI image generator"""


# Singleton instance for backward compatibility
_instance = Step1Brief()


def run(run_dir: Path) -> Dict[str, Any]:
    """Load questionnaire, build brief with LLM, return JSON.

    Step 1 always runs once and outputs a single file (step1_brief.json).
    For sequences, the brief contains a sequence_narrative_arc + emails[] array.
    """
    return _instance.run(run_dir, email_num=1, total_emails=1)
