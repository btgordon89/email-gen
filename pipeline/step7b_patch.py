"""Step 7b: HTML Patch Agent — apply surgical fixes to email_final.html based on step7 review feedback."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List

from . import anthropic_text, audit, config, gemini_text, io_util

EMAIL_HTML_FILENAME = "email_final.html"
PRE_PATCH_FILENAME = "email_pre_patch.html"
SCREENSHOT_PATCHED_FILENAME = "email_screenshot_patched.png"

STEP_ID = "step7b_patch"

DEFAULT_SCHEMA: Dict[str, Any] = {
    "patches_applied": [],
    "skipped": [],
    "patched_html_path": "",
    "screenshot_path": "",
}


def _render_screenshot(html_path: Path, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 600, "height": 900})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(output_path), full_page=True)
        browser.close()


def _load_system_prompt() -> str:
    prompt_path = config.root() / "pipeline" / "prompts" / f"{STEP_ID}.system.md"
    if not prompt_path.is_file():
        return ""
    return prompt_path.read_text(encoding="utf-8")


def _build_prompt(review: Dict[str, Any], html: str) -> str:
    weaknesses = review.get("weaknesses", [])
    recommendations = review.get("recommendations", [])
    section_issues = [
        f"{s['section']} (score {s['score']}): {s['notes']}"
        for s in review.get("section_feedback", [])
        if s.get("score", 10) < 8
    ]

    feedback_block = json.dumps(
        {
            "overall_score": review.get("overall_score"),
            "weaknesses": weaknesses,
            "section_issues": section_issues,
            "recommendations": recommendations,
            "cta_effectiveness": review.get("cta_effectiveness", ""),
            "visual_hierarchy": review.get("visual_hierarchy", ""),
            "mobile_considerations": review.get("mobile_considerations", ""),
        },
        indent=2,
    )

    return f"""Apply targeted HTML/CSS fixes to the email below based on the visual review feedback.

## REVIEW FEEDBACK
{feedback_block}

## CURRENT HTML
{html}"""


def _extract_html(raw: str) -> str:
    """Strip markdown fences if Gemini wraps the HTML in ```html ... ```."""
    # Match ```html ... ``` or ``` ... ```
    fenced = re.search(r"```(?:html)?\s*\n([\s\S]+?)\n```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    # If it starts with <!DOCTYPE or <html, return as-is
    stripped = raw.strip()
    if stripped.lower().startswith("<!doctype") or stripped.lower().startswith("<html"):
        return stripped
    return raw.strip()


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """
    Read step7 review feedback, patch email_final.html with targeted fixes,
    save a new screenshot, and write the patch report.

    Outputs:
        run_dir/email_pre_patch.html          — backup of original
        run_dir/email_final.html              — patched version (overwrites)
        run_dir/email_screenshot_patched.png  — screenshot after patching
        run_dir/step7b_patch.json             — patch report
        run_dir/audit/step7b_patch.audit.json
    """
    start_time = time.time()
    warnings: List[str] = []

    # Determine per-email filenames in sequence mode
    if total_emails > 1:
        html_filename = f"email_{email_num}_final.html"
        pre_patch_filename = f"email_{email_num}_pre_patch.html"
        screenshot_filename = f"email_{email_num}_screenshot_patched.png"
        review_filename = io_util.step_filename(io_util.STEP7, email_num, total_emails)
        output_filename = io_util.step_filename(io_util.STEP7B, email_num, total_emails)
        audit_step_id = f"step7b_patch_email_{email_num}"
    else:
        html_filename = EMAIL_HTML_FILENAME
        pre_patch_filename = PRE_PATCH_FILENAME
        screenshot_filename = SCREENSHOT_PATCHED_FILENAME
        review_filename = io_util.STEP7
        output_filename = io_util.STEP7B
        audit_step_id = STEP_ID

    # Load review
    review_path = run_dir / review_filename
    if not review_path.is_file():
        raise FileNotFoundError(
            f"{review_filename} not found at {review_path}. Run step7 (review) first."
        )
    review = io_util.read_json(review_path)

    # Load current HTML
    html_path = run_dir / html_filename
    if not html_path.is_file():
        raise FileNotFoundError(f"{html_filename} not found at {html_path}.")
    original_html = html_path.read_text(encoding="utf-8")

    # Back up original before touching it
    pre_patch_path = run_dir / pre_patch_filename
    shutil.copy2(html_path, pre_patch_path)
    print(f"[step7b] Backed up original → {pre_patch_path.name}")

    # Build prompt + system
    prompt = _build_prompt(review, original_html)
    system = _load_system_prompt()
    model = config.patch_model()

    # Call LLM (route to Anthropic or Gemini based on model name)
    provider = "Claude" if model.startswith("claude-") else "Gemini"
    print(f"[step7b] Sending to {provider} ({model}) for surgical patching...")
    if model.startswith("claude-"):
        raw_response = anthropic_text.generate_text(
            prompt=prompt,
            model=model,
            system=system if system else None,
        )
    else:
        raw_response = gemini_text.generate_text(
            prompt=prompt,
            model=model,
            system=system if system else None,
        )

    # Extract the patched HTML from the response
    patched_html = _extract_html(raw_response)

    if not patched_html.strip():
        warnings.append("Gemini returned empty HTML — keeping original")
        patched_html = original_html

    # Basic sanity check: ensure Klaviyo tags weren't mangled
    original_klaviyo_tags = re.findall(r"\{%[^%]+%\}", original_html)
    patched_klaviyo_tags = re.findall(r"\{%[^%]+%\}", patched_html)
    if set(original_klaviyo_tags) != set(patched_klaviyo_tags):
        warnings.append(
            f"Klaviyo tag mismatch after patch — original had {len(original_klaviyo_tags)}, "
            f"patched has {len(patched_klaviyo_tags)}. Review carefully."
        )

    # Write patched HTML
    html_path.write_text(patched_html, encoding="utf-8")
    print(f"[step7b] Patched HTML written → {html_path.name}")

    # Re-render screenshot
    screenshot_path = run_dir / screenshot_filename
    print(f"[step7b] Rendering patched screenshot → {screenshot_path.name}")
    _render_screenshot(html_path, screenshot_path)
    print(f"[step7b] Patched screenshot saved ({screenshot_path.stat().st_size // 1024} KB)")

    # We can't automatically know what patches were applied without asking Gemini separately.
    # Instead, extract a summary from the raw response if Gemini included one before the HTML.
    patches_applied: List[str] = []
    skipped: List[str] = []
    # Look for a JSON block in the response that might contain patch notes
    json_match = re.search(r"\{[\s\S]*?\"patches_applied\"[\s\S]*?\}", raw_response)
    if json_match:
        try:
            notes = json.loads(json_match.group())
            patches_applied = notes.get("patches_applied", [])
            skipped = notes.get("skipped", [])
        except json.JSONDecodeError:
            pass

    out: Dict[str, Any] = {
        "patches_applied": patches_applied,
        "skipped": skipped,
        "pre_patch_path": str(pre_patch_path),
        "patched_html_path": str(html_path),
        "screenshot_path": str(screenshot_path),
        "klaviyo_tag_warnings": warnings,
    }

    output_path = run_dir / output_filename
    io_util.write_json(output_path, out)
    print(f"[step7b] Patch report saved → {output_path.name}")

    # Audit log
    duration = time.time() - start_time
    audit.write_audit_log(
        run_dir=run_dir,
        step_id=audit_step_id,
        model=model,
        prompt=prompt,
        system_prompt=system,
        raw_response=raw_response,
        parsed_output=out,
        duration_seconds=duration,
        warnings=warnings,
        metadata={
            "original_html_size_bytes": len(original_html.encode()),
            "patched_html_size_bytes": len(patched_html.encode()),
            "screenshot_path": str(screenshot_path),
        },
    )

    return out
