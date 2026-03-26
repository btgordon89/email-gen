"""Klaviyo API client for image uploads and template management."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from . import config


def _api_key() -> str:
    import os
    key = os.getenv("KLAVIYO_API_KEY", "").strip()
    if not key:
        raise ValueError("Set KLAVIYO_API_KEY in .env")
    return key


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Klaviyo-API-Key {_api_key()}",
        "accept": "application/vnd.api+json",
        "revision": "2025-01-15",
    }


def upload_image(
    file_path: Path,
    name: Optional[str] = None,
    hidden: bool = False,
    retry_count: int = 2,
) -> Dict[str, Any]:
    """
    Upload an image file to Klaviyo's CDN.
    
    Returns dict with:
      - image_url: hosted URL
      - image_id: Klaviyo resource ID
      - format: file type
      - size: bytes
    
    Rate limits: 3/s burst, 100/m steady, 100/d daily.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Image not found: {file_path}")
    
    url = "https://a.klaviyo.com/api/image-upload"
    headers = _headers()
    # Don't set content-type; requests will set it with boundary for multipart
    headers.pop("content-type", None)
    
    display_name = name or file_path.stem
    
    files = {
        "file": (file_path.name, open(file_path, "rb"), _mime_type(file_path)),
    }
    data = {
        "name": display_name,
        "hidden": str(hidden).lower(),
    }
    
    for attempt in range(retry_count + 1):
        try:
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=90)
            
            # Rate limit handling
            if resp.status_code == 429:
                if attempt < retry_count:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
            
            resp.raise_for_status()
            body = resp.json()
            
            attrs = body.get("data", {}).get("attributes", {})
            return {
                "image_url": attrs.get("image_url", ""),
                "image_id": body.get("data", {}).get("id", ""),
                "format": attrs.get("format", ""),
                "size": attrs.get("size", 0),
                "name": attrs.get("name", ""),
            }
        
        except requests.RequestException as e:
            if attempt == retry_count:
                raise RuntimeError(f"Klaviyo image upload failed after {retry_count + 1} attempts: {e}")
            time.sleep(1)
    
    raise RuntimeError("Upload failed unexpectedly")


def _mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")


def create_template(
    name: str,
    html: str,
    text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a template in Klaviyo's template library.
    
    Returns:
      {
        "template_id": "...",
        "name": "...",
        "editor_type": "CODE",
        "created_at": "...",
        "web_url": "https://www.klaviyo.com/template/...",
      }
    
    Requires templates:write scope.
    Rate limits: 10/s burst, 150/m steady.
    """
    url = "https://a.klaviyo.com/api/templates"
    headers = _headers()
    headers["content-type"] = "application/vnd.api+json"
    
    body = {
        "data": {
            "type": "template",
            "attributes": {
                "name": name,
                "editor_type": "CODE",
                "html": html,
            }
        }
    }
    
    if text:
        body["data"]["attributes"]["text"] = text
    
    resp = requests.post(url, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    
    data = resp.json().get("data", {})
    attrs = data.get("attributes", {})
    template_id = data.get("id", "")
    
    # Construct web URL (Klaviyo UI link)
    web_url = f"https://www.klaviyo.com/template/{template_id}/edit" if template_id else ""
    
    return {
        "template_id": template_id,
        "name": attrs.get("name", ""),
        "editor_type": attrs.get("editor_type", ""),
        "created_at": attrs.get("created", ""),
        "web_url": web_url,
    }
