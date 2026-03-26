"""Step 2A: Structure Refiner — convert brief to HTML skeleton with placeholder tokens."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import base_step, config, gemini_text, io_util, validators

class Step2aStructure(base_step.BaseStep):
    """Generate HTML skeleton with token manifest."""
    
    step_id = "step2a_structure"
    output_filename = io_util.STEP2A
    model_fn = staticmethod(config.structure_model)
    default_schema = {
        "html_skeleton": "",
        "token_manifest": [],
        "responsive_notes": "",
        "design_decisions": "",
    }
    
    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load brief and base HTML components."""
        brief_path = run_dir / io_util.STEP1
        if not brief_path.is_file():
            raise FileNotFoundError(f"Step 1 brief not found: {brief_path}")

        full_brief = io_util.read_json(brief_path)
        brief = self._brief_for_email(full_brief)

        base_components_path = config.email_templates_dir() / "base_components.html"
        if not base_components_path.is_file():
            raise FileNotFoundError(f"Base components not found: {base_components_path}")

        base_components = base_components_path.read_text(encoding="utf-8")

        return {
            "brief": brief,
            "base_components": base_components,
        }
    
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build structure generation prompt."""
        brief = inputs["brief"]
        base_components = inputs["base_components"]
        
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

Generate the complete HTML skeleton with all placeholder tokens per the system schema."""
    
    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """Validate token consistency between HTML and manifest."""
        return validators.validate_structure_tokens(output)


# Singleton instance for backward compatibility
_instance = Step2aStructure()


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Load step1 brief, build HTML skeleton, return structure dict."""
    return _instance.run(run_dir, email_num=email_num, total_emails=total_emails)
