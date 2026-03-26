"""Audit logging for step executions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def write_audit_log(
    run_dir: Path,
    step_id: str,
    model: str,
    prompt: str,
    system_prompt: Optional[str],
    raw_response: str,
    parsed_output: Dict[str, Any],
    duration_seconds: float,
    warnings: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write an audit log for a step execution.
    
    Args:
        run_dir: output/<run_id>/
        step_id: e.g. "step1_brief"
        model: e.g. "gemini-2.5-pro"
        prompt: The full user prompt sent to the LLM
        system_prompt: The system instruction (may be None)
        raw_response: The raw LLM response before parsing
        parsed_output: The final parsed JSON output
        duration_seconds: How long the step took
        warnings: Any warnings/errors during execution
        metadata: Optional extra data (e.g., retry count, input file hashes)
    """
    audit_dir = run_dir / "audit"
    audit_dir.mkdir(exist_ok=True)
    
    # Compute hashes for large text fields (to detect changes without storing full text)
    prompt_hash = _hash_text(prompt)
    system_hash = _hash_text(system_prompt or "")
    response_hash = _hash_text(raw_response)
    
    audit_record = {
        "step_id": step_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "duration_seconds": round(duration_seconds, 2),
        
        # Full content (truncated if very long)
        "prompt": _truncate(prompt, max_len=8000),
        "system_prompt": _truncate(system_prompt or "", max_len=8000),
        "raw_response": _truncate(raw_response, max_len=10000),
        
        # Hashes for full content (to detect changes)
        "prompt_hash": prompt_hash,
        "system_prompt_hash": system_hash,
        "raw_response_hash": response_hash,
        
        # Parsed output (reference only — full output is in stepN.json)
        "parsed_output_keys": list(parsed_output.keys()) if isinstance(parsed_output, dict) else [],
        "parse_error": parsed_output.get("parse_error", False),
        
        # Warnings and errors
        "warnings": warnings,
        
        # Optional metadata
        "metadata": metadata or {},
    }
    
    audit_path = audit_dir / f"{step_id}.audit.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_record, f, indent=2, ensure_ascii=False)


def _hash_text(text: str) -> str:
    """Compute SHA256 hash of text (for change detection)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if truncated."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n[... truncated ...]"


def read_audit_log(run_dir: Path, step_id: str) -> Optional[Dict[str, Any]]:
    """
    Read an audit log for a step.
    
    Returns:
        Audit record dict, or None if not found
    """
    audit_path = run_dir / "audit" / f"{step_id}.audit.json"
    if not audit_path.is_file():
        return None
    
    with open(audit_path, encoding="utf-8") as f:
        return json.load(f)


def list_audit_logs(run_dir: Path) -> List[str]:
    """
    List all audit logs for a run.
    
    Returns:
        List of step_ids that have audit logs
    """
    audit_dir = run_dir / "audit"
    if not audit_dir.is_dir():
        return []
    
    logs = []
    for path in sorted(audit_dir.glob("*.audit.json")):
        step_id = path.stem.replace(".audit", "")
        logs.append(step_id)
    return logs
