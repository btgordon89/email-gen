"""Run folders and JSON artifacts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import config

STEP1 = "step1_brief.json"
STEP2A = "step2a_structure.json"
STEP2B = "step2b_discount.json"
STEP2C = "step2c_products.json"
STEP2D = "step2d_copy.json"
STEP2E = "step2e_links.json"
STEP2F = "step2f_link_check.json"
STEP3 = "step3_cohesion.json"
STEP4 = "step4_images.json"
STEP5 = "step5_assembly.json"
STEP7 = "step7_review.json"
STEP7B = "step7b_patch.json"


def ensure_output() -> Path:
    p = config.output_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def new_run_id(name: Optional[str] = None) -> str:
    if name:
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_") or "run"
        return safe
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")


def run_dir(run_id: str) -> Path:
    return ensure_output() / run_id


def init_run(run_id: str, questionnaire_path: Optional[Path] = None) -> Path:
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "images").mkdir(exist_ok=True)
    meta: Dict[str, Any] = {
        "run_id": run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    if questionnaire_path and questionnaire_path.is_file():
        dest = d / "questionnaire.yaml"
        shutil.copy2(questionnaire_path, dest)
        meta["questionnaire"] = str(dest)
    write_json(d / "meta.json", meta)
    return d


def load_meta(run_dir: Path) -> Dict[str, Any]:
    p = run_dir / "meta.json"
    if not p.is_file():
        return {}
    return read_json(p)


def patch_meta(run_dir: Path, **updates: Any) -> Dict[str, Any]:
    meta = load_meta(run_dir)
    for k, v in updates.items():
        if v is not None:
            meta[k] = v
    write_json(run_dir / "meta.json", meta)
    return meta


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_step(run_id: str, filename: str) -> Optional[Dict[str, Any]]:
    p = run_dir(run_id) / filename
    if p.exists():
        return read_json(p)
    return None


def step_filename(base: str, email_num: int = 1, total_emails: int = 1) -> str:
    """Return step output filename, with email suffix for multi-email sequences.

    Examples:
        step_filename("step2a_structure.json", 2, 3) -> "step2a_structure_email_2.json"
        step_filename("step2a_structure.json", 1, 1) -> "step2a_structure.json"  (unchanged)
    """
    if total_emails <= 1:
        return base
    stem, ext = base.rsplit(".", 1)
    return f"{stem}_email_{email_num}.{ext}"
