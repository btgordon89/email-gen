"""Step 2F: Link Checker — HTTP-validate all URLs produced by step 2E."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import requests

from . import io_util

# Tokens whose values are Klaviyo placeholders, not real URLs — skip these
_KLAVIYO_TOKENS = {"{{unsubscribe_link}}", "{{preferences_link}}"}

# A value that itself looks like a Klaviyo template tag
def _is_klaviyo_placeholder(url: str) -> bool:
    if not url:
        return True  # treat None/empty as non-checkable, skip silently
    return url.startswith("{{") and url.endswith("}}")


def _collect_urls(links_data: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return (label, url) pairs for every real URL in the links output."""
    pairs: List[Tuple[str, str]] = []

    for token, url in links_data.get("links_by_token", {}).items():
        if token in _KLAVIYO_TOKENS or _is_klaviyo_placeholder(url):
            continue
        pairs.append((f"links_by_token[{token}]", url))

    for handle, url in links_data.get("product_links", {}).items():
        if _is_klaviyo_placeholder(url):
            continue
        pairs.append((f"product_links[{handle}]", url))

    for handle, url in links_data.get("collection_links", {}).items():
        if _is_klaviyo_placeholder(url):
            continue
        pairs.append((f"collection_links[{handle}]", url))

    return pairs


def _check_url(label: str, url: str, timeout: int = 8) -> Dict[str, Any]:
    """HEAD-check a single URL, fall back to GET on 405. Returns a result dict."""
    result: Dict[str, Any] = {"label": label, "url": url}
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            result["status"] = "invalid"
            result["error"] = "URL is missing scheme or host"
            result["ok"] = False
            return result

        resp = requests.head(url, allow_redirects=True, timeout=timeout,
                             headers={"User-Agent": "EmailLinkChecker/1.0"})
        if resp.status_code == 405:
            resp = requests.get(url, allow_redirects=True, timeout=timeout,
                                headers={"User-Agent": "EmailLinkChecker/1.0"})

        final_url = resp.url
        result["status_code"] = resp.status_code
        result["final_url"] = final_url
        result["redirected"] = (final_url.rstrip("/") != url.rstrip("/"))
        result["ok"] = (200 <= resp.status_code < 300)

    except requests.exceptions.ConnectionError as e:
        result["status"] = "connection_error"
        result["error"] = str(e)
        result["ok"] = False
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["error"] = f"No response within {timeout}s"
        result["ok"] = False
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["ok"] = False

    return result


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """HTTP-check all links from step 2E. Raises SystemExit if any link fails."""
    links_data = io_util.read_json(
        run_dir / io_util.step_filename(io_util.STEP2E, email_num, total_emails)
    )
    pairs = _collect_urls(links_data)

    results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    print(f"  Checking {len(pairs)} URLs...")
    for label, url in pairs:
        result = _check_url(label, url)
        results.append(result)
        status = result.get("status_code", result.get("status", "?"))
        ok_mark = "✓" if result["ok"] else "✗"
        print(f"    {ok_mark} [{status}] {label}: {url}")
        if result.get("redirected") and result["ok"]:
            print(f"         → redirected to: {result['final_url']}")
        if not result["ok"]:
            failures.append(result)

    output: Dict[str, Any] = {
        "total_checked": len(results),
        "total_ok": len(results) - len(failures),
        "total_failed": len(failures),
        "results": results,
        "failures": [f["label"] for f in failures],
    }

    io_util.write_json(
        run_dir / io_util.step_filename(io_util.STEP2F, email_num, total_emails), output
    )

    if failures:
        lines = [
            f"  - {f['label']}: {f['url']} "
            f"(status={f.get('status_code', f.get('status', '?'))}, "
            f"error={f.get('error', '')})"
            for f in failures
        ]
        raise SystemExit(
            f"\n✗ Link check failed — {len(failures)} broken URL(s):\n"
            + "\n".join(lines)
            + f"\n\nFix the links in {io_util.step_filename(io_util.STEP2E, email_num, total_emails)} or re-run step2e before continuing."
        )

    return output
