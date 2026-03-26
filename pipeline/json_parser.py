"""Shared JSON parsing utilities for LLM responses."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional, Tuple


def parse_llm_json(
    response: str,
    default_schema: Optional[Dict[str, Any]] = None,
    max_retries: int = 1,
    retry_fn: Optional[Callable[[str], str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse JSON from an LLM response, with automatic fence stripping and optional retry.
    
    Args:
        response: Raw LLM response text (may contain markdown fences)
        default_schema: Fallback dict to return on parse failure (with parse_error: True)
        max_retries: How many times to retry if parsing fails (0 = no retries)
        retry_fn: Optional callback to re-call LLM with error message
        
    Returns:
        (parsed_dict, warnings_list)
        
    Examples:
        # Simple parse
        data, warnings = parse_llm_json(response, {"name": "", "age": 0})
        
        # With retry
        def retry_call(error_msg):
            return llm.generate("Fix this JSON: " + error_msg)
        data, warnings = parse_llm_json(response, default_schema, max_retries=2, retry_fn=retry_call)
    """
    default_schema = default_schema or {}
    warnings: List[str] = []
    
    for attempt in range(max_retries + 1):
        text = _strip_fences(response.strip())
        
        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
            return parsed, warnings
            
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"JSON parse error (attempt {attempt + 1}/{max_retries + 1}): {e}"
            warnings.append(error_msg)
            
            # If we have retries left and a retry function, try again
            if attempt < max_retries and retry_fn:
                retry_prompt = f"Your previous response had a JSON error: {e}\n\nPlease output ONLY valid JSON, no markdown fences."
                try:
                    response = retry_fn(retry_prompt)
                    warnings.append(f"Retry {attempt + 1}: called LLM again")
                    continue
                except Exception as retry_err:
                    warnings.append(f"Retry {attempt + 1} failed: {retry_err}")
                    break
            else:
                break
    
    # All attempts failed — return default schema with error flag
    result = dict(default_schema)
    result["parse_error"] = True
    result["parse_error_message"] = warnings[-1] if warnings else "Unknown parse error"
    result["raw_response"] = response[:2000]  # Truncate to avoid huge JSON files
    
    return result, warnings


def _strip_fences(text: str) -> str:
    """
    Remove markdown code fences from LLM response.
    
    Handles:
        ```json
        {...}
        ```
        
        ```
        {...}
        ```
    """
    if "```" not in text:
        return text
    
    # Find first and last fence
    start = text.find("```")
    end = text.rfind("```")
    
    if start >= end:
        return text
    
    # Extract content between fences
    block = text[start + 3 : end].strip()
    
    # Remove language tag if present (e.g., "json")
    if block.startswith("json"):
        block = block[4:].lstrip()
    elif block.startswith("JSON"):
        block = block[4:].lstrip()
    
    return block


def validate_required_keys(
    data: Dict[str, Any],
    required_keys: List[str],
) -> List[str]:
    """
    Check that a parsed dict has all required keys.
    
    Returns:
        List of warning messages (empty if all keys present)
    """
    warnings: List[str] = []
    for key in required_keys:
        if key not in data:
            warnings.append(f"Missing required key: {key}")
    return warnings


def ensure_keys(
    data: Dict[str, Any],
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Ensure all keys from schema exist in data, setting defaults if missing.
    
    Args:
        data: Parsed JSON dict (may be incomplete)
        schema: Dict with default values for all expected keys
        
    Returns:
        data with all schema keys present
    """
    for key, default in schema.items():
        data.setdefault(key, default)
    return data
