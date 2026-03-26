#!/usr/bin/env python3
"""
preview_emails.py — Screenshot email HTML files for sharing.

Renders each email_*_final.html in the given output folder using Playwright
and saves individual PNGs. Optionally stitches them into a single combined
preview sheet (handy for sharing as one image).

Examples
--------
# Screenshot all emails in easter_2026, produce combined sheet:
python scripts/preview_emails.py --dir output/easter_2026

# Individual PNGs only, no combined sheet:
python scripts/preview_emails.py --dir output/easter_2026 --no-combine

# Custom output location and width:
python scripts/preview_emails.py --dir output/easter_2026 --width 650 --out-dir /tmp/previews
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Screenshot
# ---------------------------------------------------------------------------

def render_screenshot(html_path: Path, output_path: Path, width: int) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(output_path), full_page=True)
        browser.close()


# ---------------------------------------------------------------------------
# Combine
# ---------------------------------------------------------------------------

def combine_images(image_paths: list[Path], out_path: Path, gap: int = 40, bg: str = "#f0f0f0") -> None:
    from PIL import Image, ImageDraw

    images = [Image.open(p) for p in image_paths]
    max_w = max(img.width for img in images)
    total_h = sum(img.height for img in images) + gap * (len(images) + 1)

    sheet = Image.new("RGB", (max_w + gap * 2, total_h), bg)
    draw = ImageDraw.Draw(sheet)

    y = gap
    for img in images:
        # Center horizontally and drop a subtle shadow
        x = (max_w + gap * 2 - img.width) // 2
        draw.rectangle([x + 4, y + 4, x + img.width + 4, y + img.height + 4], fill="#cccccc")
        sheet.paste(img, (x, y))
        y += img.height + gap

    sheet.save(out_path, format="PNG", optimize=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="preview_emails",
        description="Render email HTML files to shareable PNG previews.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--dir",
        metavar="PATH",
        type=Path,
        required=True,
        help="Output folder containing email_*_final.html files.",
    )
    p.add_argument(
        "--width",
        metavar="PX",
        type=int,
        default=600,
        help="Viewport width in pixels (default: 600).",
    )
    p.add_argument(
        "--out-dir",
        metavar="PATH",
        type=Path,
        default=None,
        dest="out_dir",
        help="Where to save screenshots (default: --dir/previews/).",
    )
    p.add_argument(
        "--no-combine",
        action="store_true",
        dest="no_combine",
        help="Skip producing a combined preview sheet.",
    )
    p.add_argument(
        "--combined-name",
        metavar="FILENAME",
        default="all_emails_preview.png",
        dest="combined_name",
        help="Filename for the combined sheet (default: all_emails_preview.png).",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    run_dir = args.dir.resolve()
    if not run_dir.is_dir():
        parser.error(f"Directory not found: {run_dir}")

    html_files = sorted(run_dir.glob("email_*_final.html"))
    if not html_files:
        parser.error(f"No email_*_final.html files found in {run_dir}")

    out_dir = (args.out_dir or run_dir / "previews").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Found {len(html_files)} email(s) in {run_dir.name}")
    print(f"Output → {out_dir}\n")

    screenshots: list[Path] = []
    for html_path in html_files:
        stem = html_path.stem.replace("_final", "")
        out_path = out_dir / f"{stem}_preview.png"
        print(f"  Rendering {html_path.name} ...", end=" ", flush=True)
        render_screenshot(html_path, out_path, args.width)
        size_kb = out_path.stat().st_size // 1024
        print(f"saved ({size_kb} KB) → {out_path.name}")
        screenshots.append(out_path)

    if not args.no_combine and len(screenshots) > 1:
        combined_path = out_dir / args.combined_name
        print(f"\nCombining into sheet → {combined_path.name} ...", end=" ", flush=True)
        combine_images(screenshots, combined_path)
        size_kb = combined_path.stat().st_size // 1024
        print(f"done ({size_kb} KB)")
        print(f"\nShareable preview: {combined_path}")
    elif not args.no_combine:
        print(f"\nShareable preview: {screenshots[0]}")
    else:
        print(f"\nIndividual previews saved to: {out_dir}")


if __name__ == "__main__":
    main()
