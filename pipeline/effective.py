"""Shared logic for merging step3 revisions with step2 outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from . import io_util


def effective_copy(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """
    Get the effective copy data, merging step2d with step3 revisions.

    Returns:
        Complete copy dict with all fields (subject_line, preheader, copy_by_token, etc.)
    """
    base_copy = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2D, email_num, total_emails)
    )

    step3_path = run_dir / io_util.step_filename(io_util.STEP3, email_num, total_emails)
    if not step3_path.is_file():
        return base_copy

    s3 = io_util.read_json(step3_path)
    revised = s3.get("revised_copy")

    if not isinstance(revised, dict):
        return base_copy

    # If step3 provided revised_copy, it should be a complete replacement
    # But we'll merge token-by-token to be safe
    if revised.get("copy_by_token"):
        result = dict(base_copy)

        # Merge top-level fields from revised copy
        for key in ["subject_line", "preheader", "fine_print", "copy_rationale"]:
            if key in revised and revised[key]:
                result[key] = revised[key]

        # Merge copy_by_token (step3 wins for conflicts)
        merged_tokens = dict(base_copy.get("copy_by_token", {}))
        merged_tokens.update(revised.get("copy_by_token", {}))
        result["copy_by_token"] = merged_tokens

        # Merge product_copy if present
        if revised.get("product_copy"):
            result["product_copy"] = revised["product_copy"]

        return result

    return base_copy


def effective_links(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """
    Get the effective links data, using step3 revisions if present.

    Returns:
        Complete links dict with links_by_token, product_links, etc.
    """
    step3_path = run_dir / io_util.step_filename(io_util.STEP3, email_num, total_emails)
    if step3_path.is_file():
        s3 = io_util.read_json(step3_path)
        revised = s3.get("revised_links")
        if isinstance(revised, dict) and revised.get("links_by_token"):
            return revised

    return io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2E, email_num, total_emails)
    )


def effective_structure(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """
    Get the effective structure data, merging step2a with step3 revisions.

    Returns:
        Complete structure dict with html_skeleton, token_manifest, etc.
    """
    base = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2A, email_num, total_emails)
    )

    step3_path = run_dir / io_util.step_filename(io_util.STEP3, email_num, total_emails)
    if not step3_path.is_file():
        return base

    s3 = io_util.read_json(step3_path)
    revised = s3.get("revised_structure")

    if not isinstance(revised, dict):
        return base

    result = dict(base)

    # Merge token_manifest if revised
    if revised.get("token_manifest"):
        result["token_manifest"] = revised["token_manifest"]

    # Merge html_skeleton if revised
    if revised.get("html_skeleton"):
        result["html_skeleton"] = revised["html_skeleton"]

    return result
