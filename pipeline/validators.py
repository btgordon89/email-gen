"""Inter-step validation utilities."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set


def validate_structure_tokens(structure: Dict[str, Any]) -> List[str]:
    """
    Validate that step2a structure has consistent tokens between HTML and manifest.
    
    Checks:
    - Every {{token}} in HTML appears in token_manifest
    - Every token in token_manifest appears in HTML
    
    Returns:
        List of validation warnings
    """
    warnings: List[str] = []
    
    html = structure.get("html_skeleton", "")
    manifest = structure.get("token_manifest", [])
    
    if not html or not manifest:
        return warnings
    
    # Extract all {{tokens}} from HTML
    html_tokens = set(re.findall(r'\{\{[^}]+\}\}', html))
    
    # Extract all tokens from manifest
    manifest_tokens = {entry.get("token", "") for entry in manifest if entry.get("token")}
    
    # Check for tokens in HTML but not in manifest
    orphan_html = html_tokens - manifest_tokens
    if orphan_html:
        warnings.append(f"Tokens in HTML but not in manifest: {sorted(orphan_html)}")
    
    # Check for tokens in manifest but not in HTML
    orphan_manifest = manifest_tokens - html_tokens
    if orphan_manifest:
        warnings.append(f"Tokens in manifest but not in HTML: {sorted(orphan_manifest)}")
    
    return warnings


def validate_copy_completeness(
    copy: Dict[str, Any],
    structure: Dict[str, Any],
) -> List[str]:
    """
    Validate that step2d copy has filled all required tokens from step2a structure.
    
    Checks:
    - Every token with source_agent="copy" in manifest has a corresponding entry in copy_by_token
    
    Returns:
        List of validation warnings
    """
    warnings: List[str] = []
    
    manifest = structure.get("token_manifest", [])
    copy_by_token = copy.get("copy_by_token", {})
    
    # Find all copy tokens in manifest
    copy_tokens = {
        entry.get("token", "")
        for entry in manifest
        if entry.get("source_agent") == "copy" and entry.get("token")
    }
    
    # Normalize copy_by_token keys (add {{ }} if missing)
    normalized_copy = {}
    for key, value in copy_by_token.items():
        if not key.startswith("{{"):
            key = f"{{{{{key}}}}}"
        normalized_copy[key] = value
    
    provided_tokens = set(normalized_copy.keys())
    
    # Check for missing copy tokens
    missing = copy_tokens - provided_tokens
    if missing:
        warnings.append(f"Copy missing for {len(missing)} token(s): {sorted(missing)}")
    
    return warnings


def validate_links_completeness(
    links: Dict[str, Any],
    structure: Dict[str, Any],
) -> List[str]:
    """
    Validate that step2e links has filled all required tokens from step2a structure.
    
    Checks:
    - Every token with source_agent="link" in manifest has a corresponding entry in links_by_token
    
    Returns:
        List of validation warnings
    """
    warnings: List[str] = []
    
    manifest = structure.get("token_manifest", [])
    links_by_token = links.get("links_by_token", {})
    
    # Find all link tokens in manifest
    link_tokens = {
        entry.get("token", "")
        for entry in manifest
        if entry.get("source_agent") == "link" and entry.get("token")
    }
    
    # Normalize links_by_token keys (add {{ }} if missing)
    normalized_links = {}
    for key, value in links_by_token.items():
        if not key.startswith("{{"):
            key = f"{{{{{key}}}}}"
        normalized_links[key] = value
    
    provided_tokens = set(normalized_links.keys())
    
    # Check for missing link tokens
    missing = link_tokens - provided_tokens
    if missing:
        warnings.append(f"Links missing for {len(missing)} token(s): {sorted(missing)}")
    
    return warnings


def validate_cohesion_revisions(
    cohesion: Dict[str, Any],
    structure: Dict[str, Any],
) -> List[str]:
    """
    Validate that step3 cohesion revisions don't drop required tokens.
    
    Checks:
    - If revised_copy is provided, it has all required copy tokens
    - If revised_links is provided, it has all required link tokens
    
    Returns:
        List of validation warnings
    """
    warnings: List[str] = []
    
    manifest = structure.get("token_manifest", [])
    
    # Check revised_copy
    revised_copy = cohesion.get("revised_copy")
    if isinstance(revised_copy, dict) and revised_copy.get("copy_by_token"):
        copy_tokens = {
            entry.get("token", "")
            for entry in manifest
            if entry.get("source_agent") == "copy" and entry.get("token")
        }
        
        provided = set(revised_copy.get("copy_by_token", {}).keys())
        # Normalize provided tokens
        provided = {k if k.startswith("{{") else f"{{{{{k}}}}}" for k in provided}
        
        missing = copy_tokens - provided
        if missing:
            warnings.append(f"Revised copy missing {len(missing)} token(s): {sorted(missing)}")
    
    # Check revised_links
    revised_links = cohesion.get("revised_links")
    if isinstance(revised_links, dict) and revised_links.get("links_by_token"):
        link_tokens = {
            entry.get("token", "")
            for entry in manifest
            if entry.get("source_agent") == "link" and entry.get("token")
        }
        
        provided = set(revised_links.get("links_by_token", {}).keys())
        # Normalize provided tokens
        provided = {k if k.startswith("{{") else f"{{{{{k}}}}}" for k in provided}
        
        missing = link_tokens - provided
        if missing:
            warnings.append(f"Revised links missing {len(missing)} token(s): {sorted(missing)}")
    
    return warnings


def validate_assembly_readiness(
    run_dir,
    structure: Dict[str, Any],
    copy: Dict[str, Any],
    links: Dict[str, Any],
    images: Dict[str, Any],
) -> List[str]:
    """
    Pre-flight check before step5 assembly: ensure all tokens can be resolved.
    
    Returns:
        List of validation warnings
    """
    warnings: List[str] = []
    
    manifest = structure.get("token_manifest", [])
    copy_by_token = copy.get("copy_by_token", {})
    links_by_token = links.get("links_by_token", {})
    images_by_token = images.get("images_by_token", {})
    alts_by_token = images.get("alts_by_token", {})
    
    # Normalize all token dicts
    def normalize_dict(d: Dict) -> Set[str]:
        result = set()
        for key in d.keys():
            if not key.startswith("{{"):
                key = f"{{{{{key}}}}}"
            result.add(key)
        return result
    
    provided_copy = normalize_dict(copy_by_token)
    provided_links = normalize_dict(links_by_token)
    provided_images = normalize_dict(images_by_token)
    provided_alts = normalize_dict(alts_by_token)
    
    # Check each token in manifest
    for entry in manifest:
        token = entry.get("token", "")
        if not token:
            continue
        
        source = entry.get("source_agent", "")
        
        if source == "copy" and token not in provided_copy:
            warnings.append(f"Cannot resolve {token} (copy agent)")
        elif source == "link" and token not in provided_links:
            warnings.append(f"Cannot resolve {token} (link agent)")
        elif source == "image":
            # Check if it's an alt token or image token
            if token.replace("{", "").replace("}", "").endswith("_alt"):
                if token not in provided_alts:
                    warnings.append(f"Cannot resolve {token} (alt text)")
            else:
                if token not in provided_images:
                    warnings.append(f"Cannot resolve {token} (image)")
        # Note: static and discount tokens are handled by assembly, not validated here
    
    return warnings
