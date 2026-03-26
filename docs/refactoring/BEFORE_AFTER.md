# Before & After: Step File Comparison

This document shows a side-by-side comparison of step files before and after the refactoring, demonstrating the dramatic simplification.

## Example: step2d_copy.py

### BEFORE (187 lines)

```python
"""Step 2D: Copy Generator — write all email text content."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import config, gemini_text, io_util, questionnaire as questionnaire_module

STEP2D_SYSTEM = """You are an expert email copywriter for Yay's Beef Crisps..."""  # 48 lines of system prompt hardcoded here


def _build_prompt(
    brief: Dict,
    structure: Dict,
    discount: Dict,
    products: Dict,
    questionnaire: Dict,
    brand_identity: str,
) -> str:
    # 60 lines of prompt building logic
    ...


def _parse_json(response: str) -> Dict[str, Any]:
    # 20 lines of fence stripping and JSON parsing (duplicated in 6 other files!)
    text = response.strip()
    if "```" in text:
        start = text.find("```")
        end = text.rfind("```")
        if start < end:
            block = text[start + 3 : end].strip()
            if block.startswith("json"):
                block = block[4:].lstrip()
            text = block
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "parse_error": True,
            "raw_response": response[:2000],
            "subject_line": "",
            "preheader": "",
            "copy_by_token": {},
            "product_copy": {},
            "fine_print": "",
            "copy_rationale": "",
        }


def run(run_dir: Path) -> Dict[str, Any]:
    """Generate all email copy."""
    # 10 lines of loading inputs
    brief = io_util.read_json(run_dir / io_util.STEP1)
    structure = io_util.read_json(run_dir / io_util.STEP2A)
    discount = io_util.read_json(run_dir / io_util.STEP2B)
    products = io_util.read_json(run_dir / io_util.STEP2C)
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")

    focus = questionnaire.get("product_focus", "")
    pc = focus if focus not in ("all", "") else None
    brand_identity = gemini_text.load_brand_identity_text(product_category=pc)

    # Call LLM
    prompt = _build_prompt(brief, structure, discount, products, questionnaire, brand_identity)
    raw = gemini_text.generate_text(
        prompt=prompt,
        model=config.copy_model(),
        system=STEP2D_SYSTEM,
    )

    # Parse and set defaults (7 lines of boilerplate)
    copy_data = _parse_json(raw)
    copy_data.setdefault("subject_line", "")
    copy_data.setdefault("preheader", "")
    copy_data.setdefault("copy_by_token", {})
    copy_data.setdefault("product_copy", {})
    copy_data.setdefault("fine_print", "")
    copy_data.setdefault("copy_rationale", "")

    # Write output (no audit logging)
    io_util.write_json(run_dir / io_util.STEP2D, copy_data)
    return copy_data
```

**Problems**:
- System prompt buried in Python code (hard to review)
- `_parse_json()` duplicated across 6 files
- No audit trail
- No validation
- Lots of boilerplate: defaults, error handling, file I/O

---

### AFTER (92 lines)

```python
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
    model_fn = config.copy_model
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
        brief = io_util.read_json(run_dir / io_util.STEP1)
        structure = io_util.read_json(run_dir / io_util.STEP2A)
        discount = io_util.read_json(run_dir / io_util.STEP2B)
        products = io_util.read_json(run_dir / io_util.STEP2C)
        questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")
        
        focus = questionnaire.get("product_focus", "")
        pc = focus if focus not in ("all", "") else None
        brand_identity = gemini_text.load_brand_identity_text(product_category=pc)
        
        return {
            "brief": brief,
            "structure": structure,
            "discount": discount,
            "products": products,
            "questionnaire": questionnaire,
            "brand_identity": brand_identity,
        }
    
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build copy generation prompt."""
        # 60 lines of prompt building logic (same as before)
        ...
    
    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """Validate that all required copy tokens are filled."""
        return validators.validate_copy_completeness(output, inputs["structure"])


# Singleton instance for backward compatibility
_instance = Step2dCopy()


def run(run_dir: Path) -> Dict[str, Any]:
    """Generate all email copy."""
    return _instance.run(run_dir)
```

**System prompt now in**: `pipeline/prompts/step2d_copy.system.md` (48 lines, version-controlled markdown)

**What the base class handles automatically**:
- ✅ Loading system prompt from `prompts/step2d_copy.system.md`
- ✅ Calling LLM with retry logic
- ✅ Parsing JSON response (fence stripping, error handling)
- ✅ Setting default values from `default_schema`
- ✅ Calling `validate()` hook
- ✅ Writing output JSON
- ✅ Writing audit log with full trace

---

## The Difference

### Before
- 187 lines total
- System prompt hardcoded in Python (48 lines)
- Duplicate `_parse_json()` function (20 lines)
- Manual default setting (7 lines)
- No validation
- No audit trail

### After
- 92 lines total (51% reduction!)
- System prompt in external `.md` file (reviewable by non-engineers)
- Shared `json_parser` module (used by all steps)
- Automatic default setting by base class
- **Validation hook** catches missing tokens
- **Audit trail** for every execution

### What You Write Now
Just **3 methods**:
1. `load_inputs()` — What data does this step need?
2. `build_prompt()` — What prompt should we send to the LLM?
3. `validate()` — Any custom validation? (optional)

Everything else is automatic!

---

## Code Reuse Stats

### Eliminated Duplication

| Pattern | Before | After |
|---------|--------|-------|
| JSON parsing (`_parse_json`) | 7 copies | 1 shared |
| Effective state merge | 2 copies (step4, step5) | 1 shared |
| System prompts in code | 7 hardcoded strings | 7 `.md` files |
| Default value setting | 7 manual blocks | Base class |
| Audit logging | None | Base class |
| Validation | None | Validator functions |

### Lines Saved Per Step

| Step | Before | After | Reduction |
|------|--------|-------|-----------|
| step1_brief | 160 | 75 | 53% |
| step2a_structure | 251 | 103 | 59% |
| step2d_copy | 187 | 92 | 51% |
| step2e_links | 172 | 108 | 37% |
| step3_cohesion | 193 | 107 | 45% |

**Average reduction**: 49% per step file!

---

## What You Get for Free Now

Every step automatically gets:

1. **Audit Trail** 
   - Full prompt + response
   - Duration tracking
   - Error logging
   - Model version

2. **Validation**
   - Custom per-step hooks
   - Standardized error reporting
   - Warnings in audit log

3. **Error Handling**
   - JSON parse failures handled gracefully
   - Automatic retry support (if configured)
   - Default fallback values

4. **Maintainability**
   - System prompts in markdown
   - Single source of truth for common logic
   - Clear extension points

5. **Testing**
   - Consistent interface
   - Mockable inputs
   - Verifiable outputs

---

## Adding a New Step (Example)

Want to add step2f_social_proof? Just:

```python
class Step2fSocialProof(base_step.BaseStep):
    step_id = "step2f_social_proof"
    output_filename = "step2f_social_proof.json"
    model_fn = config.social_proof_model
    default_schema = {"testimonials": [], "trust_badges": []}
    
    def load_inputs(self, run_dir):
        # What do you need?
        return {"brief": ..., "products": ...}
    
    def build_prompt(self, inputs):
        # What should the LLM do?
        return f"Generate social proof for: {inputs['brief']}"
```

That's it! The base class handles everything else.

Create `prompts/step2f_social_proof.system.md` with your system prompt, and you're done. Audit logging, JSON parsing, validation, error handling — all automatic.
