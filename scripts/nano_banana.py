#!/usr/bin/env python3
"""
Nano Banana — ad hoc image regeneration tool.

Regenerate any campaign image with a custom prompt and/or different reference
images, then optionally patch the result back into an HTML file.

Examples
--------
# Regenerate email 2 hero using same audit prompt, new ref image:
python scripts/nano_banana.py \
    --audit output/easter_2026/audit/step4_images.audit.json \
    --token "{{hero_banner_image}}" \
    --ref brand/assets/product_images/crispy_beef_bits/original/image_2.jpg \
    --out output/easter_2026/images/email_2/hero_banner_image.png \
    --html output/easter_2026/email_2_final.html \
    --old-src "file:///home/ben/projects/static_ads_gen/brand/assets/product_images/crispy_beef_bits/original/image_2.jpg"

# Freeform prompt, no audit:
python scripts/nano_banana.py \
    --prompt "Wide lifestyle shot of crispy beef bits on a sunny Easter brunch table..." \
    --ref path/to/ref1.jpg \
    --ref path/to/ref2.jpg \
    --out output/my_image.png
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve project root so pipeline imports work regardless of cwd
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline import gemini_image  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_prompt_from_audit(audit_path: Path, token: str) -> str:
    """Extract the generation prompt for *token* from a step4 audit JSON."""
    data = json.loads(audit_path.read_text())
    generations = data.get("image_generations", [])
    for entry in generations:
        if entry.get("token") == token:
            prompt = entry.get("prompt")
            if prompt:
                return prompt
            raise ValueError(
                f"Token '{token}' found in audit but has no prompt "
                f"(generation_method was probably 'copied' or 'downloaded')."
            )
    raise ValueError(
        f"Token '{token}' not found in audit file.\n"
        f"Available tokens: {[e.get('token') for e in generations]}"
    )


def patch_html(html_path: Path, old_src: str, new_src: str) -> None:
    """Replace *old_src* with *new_src* in the HTML file (in-place)."""
    text = html_path.read_text()
    if old_src not in text:
        print(f"  Warning: old-src not found in HTML — no patch applied.")
        print(f"  Looked for: {old_src}")
        return
    patched = text.replace(old_src, new_src)
    html_path.write_text(patched)
    count = text.count(old_src)
    print(f"  Patched {count} occurrence(s) in {html_path.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nano_banana",
        description="Ad hoc Nano Banana image regeneration.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Prompt source (mutually exclusive group)
    prompt_group = p.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument(
        "--prompt",
        metavar="TEXT",
        help="Prompt text to send to Gemini.",
    )
    prompt_group.add_argument(
        "--audit",
        metavar="PATH",
        type=Path,
        help="Path to a step4 audit JSON. Reads the prompt for --token.",
    )

    p.add_argument(
        "--token",
        metavar="TOKEN",
        default=None,
        help=(
            "Image token to look up in the audit file, e.g. '{{hero_banner_image}}'."
            " Required when --audit is used."
        ),
    )

    p.add_argument(
        "--append",
        metavar="TEXT",
        default=None,
        help="Extra instructions appended to the prompt (useful with --audit to refine without rewriting).",
    )

    p.add_argument(
        "--ref",
        metavar="PATH",
        action="append",
        type=Path,
        default=[],
        dest="refs",
        help="Reference image path. Repeat for multiple refs.",
    )

    p.add_argument(
        "--out",
        metavar="PATH",
        type=Path,
        required=True,
        help="Output image path (PNG or JPG).",
    )

    p.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help="Override the Gemini model (default: from config / env).",
    )

    # HTML patching
    p.add_argument(
        "--html",
        metavar="PATH",
        type=Path,
        default=None,
        help="HTML file to patch after generation.",
    )
    p.add_argument(
        "--old-src",
        metavar="SRC",
        default=None,
        dest="old_src",
        help=(
            "The exact img src string to replace in --html."
            " Use 'auto' to derive from --token + audit reference_images."
        ),
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Resolve prompt
    # ------------------------------------------------------------------
    if args.audit:
        if not args.token:
            parser.error("--token is required when --audit is used.")
        audit_path = args.audit.resolve()
        if not audit_path.exists():
            parser.error(f"Audit file not found: {audit_path}")
        print(f"Reading prompt from audit: {audit_path.name}  token={args.token}")
        prompt = load_prompt_from_audit(audit_path, args.token)
    else:
        prompt = args.prompt

    if args.append:
        prompt = prompt + "\n\n" + args.append
    print(f"Prompt length: {len(prompt)} chars")

    # ------------------------------------------------------------------
    # 2. Validate ref images
    # ------------------------------------------------------------------
    refs = []
    for ref in args.refs:
        p = ref.resolve()
        if not p.exists():
            # Try relative to project root
            p = (PROJECT_ROOT / ref).resolve()
        if not p.exists():
            parser.error(f"Reference image not found: {ref}")
        refs.append(p)
        print(f"  Ref: {p}")

    # ------------------------------------------------------------------
    # 3. Generate
    # ------------------------------------------------------------------
    out_path = args.out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating image → {out_path} ...")
    t0 = time.time()
    image_bytes = gemini_image.generate_image_bytes(
        prompt=prompt,
        image_inputs=refs or None,
        model=args.model,
    )
    duration = round(time.time() - t0, 2)

    suffix = out_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img.save(out_path, format="JPEG", quality=92)
    else:
        out_path.write_bytes(image_bytes)

    print(f"Saved: {out_path}  ({len(image_bytes):,} bytes)  {duration}s")

    # Write sidecar audit so every nano_banana run is traceable
    audit_record = {
        "tool": "nano_banana",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": args.model or "default (from config)",
        "output_path": str(out_path),
        "image_bytes": len(image_bytes),
        "duration_seconds": duration,
        "prompt": prompt,
        "reference_images": [str(r) for r in refs],
        "source_audit": str(args.audit.resolve()) if args.audit else None,
        "source_token": args.token if args.audit else None,
        "append": args.append,
    }
    audit_out = out_path.with_suffix(".nb_audit.json")
    audit_out.write_text(json.dumps(audit_record, indent=2))
    print(f"Audit:  {audit_out}")

    # ------------------------------------------------------------------
    # 4. Optionally patch HTML
    # ------------------------------------------------------------------
    if args.html:
        html_path = args.html.resolve()
        if not html_path.exists():
            print(f"Warning: HTML file not found, skipping patch: {html_path}")
        else:
            old_src = args.old_src
            if not old_src:
                parser.error("--old-src is required when --html is used.")
            # Embed as base64 data URI — renders reliably regardless of how the HTML is opened
            import base64
            mime = "image/jpeg" if out_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            b64 = base64.b64encode(out_path.read_bytes()).decode()
            new_src = f"data:{mime};base64,{b64}"
            print(f"\nPatching HTML: {html_path.name}")
            print(f"  Embedding {out_path.name} as base64 data URI ({len(b64) // 1024}KB encoded)")
            patch_html(html_path, old_src, new_src)

    print("\nDone.")


if __name__ == "__main__":
    main()
