"""Step 6: Upload template to Klaviyo — final deliverable."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from . import io_util, klaviyo_client, questionnaire as questionnaire_module


def run(
    run_dir: Path,
    template_name_override: str = "",
    email_num: int = 1,
    total_emails: int = 1,
) -> Dict[str, Any]:
    """
    Upload email_final.html (or email_N_final.html) as a Klaviyo template.

    Returns:
      {
        "template_id": "...",
        "template_name": "...",
        "web_url": "https://www.klaviyo.com/template/.../edit",
        "created_at": "...",
      }
    """
    step5_filename = io_util.step_filename(io_util.STEP5, email_num, total_emails)
    step5 = io_util.read_json(run_dir / step5_filename)
    final_path = Path(step5.get("email_final_path", ""))

    if not final_path.is_file():
        raise FileNotFoundError(f"email_final.html not found: {final_path}")

    html = final_path.read_text(encoding="utf-8")

    # Template name
    questionnaire = questionnaire_module.load(run_dir / "questionnaire.yaml")
    if template_name_override:
        name = template_name_override
    else:
        theme = questionnaire.get("email_theme", "Email Campaign")
        run_id = run_dir.name
        if total_emails > 1:
            name = f"{theme} — Email {email_num} of {total_emails} — {run_id}"
        else:
            name = f"{theme} — {run_id}"

    # Upload to Klaviyo
    result = klaviyo_client.create_template(name=name, html=html)

    out = {
        "template_id": result["template_id"],
        "template_name": result["name"],
        "web_url": result["web_url"],
        "editor_type": result["editor_type"],
        "created_at": result["created_at"],
        "klaviyo_ready": True,
    }

    output_filename = (
        f"step6_template_email_{email_num}.json" if total_emails > 1 else "step6_template.json"
    )
    io_util.write_json(run_dir / output_filename, out)
    return out
