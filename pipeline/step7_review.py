"""Step 7: Visual Presentation Review — screenshot the final email and critique it with Gemini vision."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image

from . import anthropic_text, audit, config, gemini_text, io_util, json_parser

# Where the final email HTML lives (relative to run_dir)
EMAIL_HTML_FILENAME = "email_final.html"
# Where the screenshot is saved (relative to run_dir)
SCREENSHOT_FILENAME = "email_screenshot.png"

STEP_ID = "step7_review"

DEFAULT_SCHEMA: Dict[str, Any] = {
    "overall_score": 0,
    "overall_impression": "",
    "first_impression": "",
    "strengths": [],
    "weaknesses": [],
    "section_feedback": [],
    "cta_effectiveness": "",
    "visual_hierarchy": "",
    "mobile_considerations": "",
    "recommendations": [],
}


def _render_screenshot(html_path: Path, output_path: Path) -> None:
    """Use Playwright headless Chromium to render the HTML and capture a full-page screenshot."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 600px is standard email client width
        page = browser.new_page(viewport={"width": 600, "height": 900})
        page.goto(f"file://{html_path.resolve()}")
        # Wait for images and web fonts to finish loading
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(output_path), full_page=True)
        browser.close()


def _load_system_prompt() -> str:
    prompt_path = config.root() / "pipeline" / "prompts" / f"{STEP_ID}.system.md"
    if not prompt_path.is_file():
        return ""
    return prompt_path.read_text(encoding="utf-8")


def _build_prompt() -> str:
    return (
        "You have been sent a promotional marketing email. "
        "The screenshot above shows exactly how it would appear in an email client at standard width (600px). "
        "Review it honestly as if you are the target customer receiving this in your inbox. "
        "Return your feedback as valid JSON matching the schema in your instructions."
    )


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """
    Render email_final.html to a screenshot, send to Gemini vision, save feedback.

    Outputs:
        run_dir/email_screenshot.png  — the rendered screenshot
        run_dir/step7_review.json     — structured feedback from Gemini
        run_dir/audit/step7_review.audit.json
    """
    start_time = time.time()
    warnings: List[str] = []

    # Determine per-email filenames in sequence mode
    if total_emails > 1:
        html_filename = f"email_{email_num}_final.html"
        screenshot_filename = f"email_{email_num}_screenshot.png"
        output_filename = io_util.step_filename(io_util.STEP7, email_num, total_emails)
        audit_step_id = f"step7_review_email_{email_num}"
    else:
        html_filename = EMAIL_HTML_FILENAME
        screenshot_filename = SCREENSHOT_FILENAME
        output_filename = io_util.STEP7
        audit_step_id = STEP_ID

    html_path = run_dir / html_filename
    if not html_path.is_file():
        raise FileNotFoundError(
            f"{html_filename} not found at {html_path}. Run step5 (assembly) first."
        )

    # 1. Render screenshot
    screenshot_path = run_dir / screenshot_filename
    print(f"[step7] Rendering screenshot → {screenshot_path}")
    _render_screenshot(html_path, screenshot_path)
    print(f"[step7] Screenshot saved ({screenshot_path.stat().st_size // 1024} KB)")

    # 2. Load screenshot as PIL image for Gemini multimodal
    screenshot_image = Image.open(screenshot_path).convert("RGB")

    # 3. Build prompt + system
    prompt = _build_prompt()
    system = _load_system_prompt()
    model = config.review_model()

    # 4. Call vision model (route to Anthropic or Gemini based on model name)
    provider = "Claude" if model.startswith("claude-") else "Gemini"
    print(f"[step7] Sending screenshot to {provider} ({model}) for visual review...")
    if model.startswith("claude-"):
        raw_response = anthropic_text.generate_text_with_images(
            prompt=prompt,
            images=[screenshot_image],
            model=model,
            system=system if system else None,
        )
    else:
        raw_response = gemini_text.generate_text_with_images(
            prompt=prompt,
            images=[screenshot_image],
            model=model,
            system=system if system else None,
        )

    # 5. Parse JSON
    parsed, parse_warnings = json_parser.parse_llm_json(
        raw_response,
        default_schema=DEFAULT_SCHEMA,
        max_retries=0,
    )
    parsed = json_parser.ensure_keys(parsed, DEFAULT_SCHEMA)
    warnings.extend(parse_warnings)

    # Attach screenshot path so callers know where it is
    parsed["screenshot_path"] = str(screenshot_path)

    # 6. Write output JSON
    output_path = run_dir / output_filename
    io_util.write_json(output_path, parsed)
    print(f"[step7] Review saved → {output_path}")

    # 7. Write audit log
    duration = time.time() - start_time
    audit.write_audit_log(
        run_dir=run_dir,
        step_id=audit_step_id,
        model=model,
        prompt=prompt,
        system_prompt=system,
        raw_response=raw_response,
        parsed_output=parsed,
        duration_seconds=duration,
        warnings=warnings,
        metadata={
            "html_path": str(html_path),
            "screenshot_path": str(screenshot_path),
            "screenshot_size_bytes": screenshot_path.stat().st_size,
        },
    )

    return parsed
