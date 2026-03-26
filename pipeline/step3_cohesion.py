"""Step 3: Cohesiveness Review — QA all outputs for consistency and quality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import base_step, config, gemini_text, io_util, questionnaire as questionnaire_module, validators


class Step3Cohesion(base_step.BaseStep):
    """Review and revise all Step 2 outputs for cohesion and consistency."""
    
    step_id = "step3_cohesion"
    output_filename = io_util.STEP3
    model_fn = staticmethod(config.cohesion_model)
    default_schema = {
        "issues_found": [],
        "revised_copy": None,
        "revised_structure": None,
        "revised_links": None,
        "cohesion_score": 5,
        "cohesion_summary": "",
    }
    
    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load all Step 2 outputs, brief, questionnaire, and brand identity."""
        full_brief = io_util.read_json(run_dir / io_util.STEP1)
        brief = self._brief_for_email(full_brief)
        structure = io_util.read_json(self._step_path(run_dir, io_util.STEP2A))
        discount = io_util.read_json(self._step_path(run_dir, io_util.STEP2B, per_email=False))
        products = io_util.read_json(self._step_path(run_dir, io_util.STEP2C))
        copy = io_util.read_json(self._step_path(run_dir, io_util.STEP2D))
        links = io_util.read_json(self._step_path(run_dir, io_util.STEP2E))
        questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")
        
        focus = questionnaire.get("product_focus", "")
        pc = focus if focus not in ("all", "") else None
        brand_identity = gemini_text.load_brand_identity_text(product_category=pc)
        
        return {
            "brief": brief,
            "structure": structure,
            "discount": discount,
            "products": products,
            "copy": copy,
            "links": links,
            "questionnaire": questionnaire,
            "brand_identity": brand_identity,
        }
    
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build cohesion review prompt."""
        brief = inputs["brief"]
        structure = inputs["structure"]
        discount = inputs["discount"]
        products = inputs["products"]
        copy = inputs["copy"]
        links = inputs["links"]
        questionnaire = inputs["questionnaire"]
        brand_identity = inputs["brand_identity"]
        
        q_summary = questionnaire_module.summarize(questionnaire)
        
        return f"""Review all email campaign components for cohesion and consistency.

ORIGINAL BRIEF:
{json.dumps(brief, indent=2)[:6000]}

QUESTIONNAIRE SUMMARY:
{q_summary}

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

Perform ALL cohesion checks per the system instructions. Return the full revised outputs."""
    
    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """Validate that revised outputs don't drop required tokens."""
        return validators.validate_cohesion_revisions(output, inputs["structure"])

# Singleton instance for backward compatibility
_instance = Step3Cohesion()


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Review all Step 2 outputs for cohesion."""
    return _instance.run(run_dir, email_num=email_num, total_emails=total_emails)
