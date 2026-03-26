#!/usr/bin/env python3
"""
Yay's Email Generator v1 — CLI (stepwise pipeline; see PRD_00_OVERVIEW.md).

Run from the email_gen directory:
  python main.py new-questionnaire [--output path/to/questionnaire.yaml]
  python main.py init-run [--name my_campaign] [--questionnaire filled.yaml]
  python main.py step4 --run RUN_ID
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import (
    brand_analysis,
    config,
    ideas as ideas_module,
    io_util,
    questionnaire,
    step1_brief,
    step2a_structure,
    step2b_discount,
    step2c_products,
    step2d_copy,
    step2e_links,
    step2f_link_check,
    step3_cohesion,
    step4_images,
    step5_assembly,
    step6_template,
    step7_review,
    step7b_patch,
)


def cmd_ideas(args: argparse.Namespace) -> None:
    output_path = Path(args.output).resolve() if args.output else None
    focus = args.product_focus or None
    print(f"→ Generating campaign ideas from customer reviews{' (' + focus + ')' if focus else ''}...")
    result = ideas_module.run(product_focus=focus, output_path=output_path)
    ideas_module.print_ideas(result)
    if output_path:
        print(f"→ Ideas saved to: {output_path}")


def cmd_brand_analysis(args: argparse.Namespace) -> None:
    inspo_dir = Path(args.inspo_dir).resolve() if args.inspo_dir else None
    output_path = Path(args.output).resolve() if args.output else None
    if inspo_dir and not inspo_dir.is_dir():
        raise SystemExit(f"Inspo directory not found: {inspo_dir}")
    print("→ Analysing brand screenshots...")
    out = brand_analysis.run(inspo_dir=inspo_dir, output_path=output_path, model=args.model or None)
    print(f"✓ Visual brand analysis written to: {out}")
    print("\nThis file is now included in every pipeline run automatically via brand_identity.")


def cmd_new_questionnaire(args: argparse.Namespace) -> None:
    out = Path(args.output).resolve()
    path = questionnaire.create_template(out)
    print(path)


def cmd_init_run(args: argparse.Namespace) -> None:
    run_id = io_util.new_run_id(args.name)
    qpath = Path(args.questionnaire).resolve() if args.questionnaire else None
    if qpath and not qpath.is_file():
        raise SystemExit(f"Questionnaire not found: {qpath}")
    d = io_util.init_run(run_id, questionnaire_path=qpath)
    print(d)


def cmd_step1(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    brief = step1_brief.run(rd)
    out = rd / io_util.STEP1
    print(f"Brief generated: {out}")
    if brief.get("parse_error"):
        print("WARNING: JSON parse error — check raw_response in output")


def cmd_step2a(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    structure = step2a_structure.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP2A, en, te)
    print(f"HTML structure generated: {out}")
    if structure.get("parse_error"):
        print("WARNING: JSON parse error — check raw_response in output")


def cmd_step2b(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    discount = step2b_discount.run(rd)  # 2B is always shared; no email_num needed
    out = rd / io_util.STEP2B
    print(f"Discount strategy generated: {out}")
    if discount.get("discount_code"):
        print(f"  Code: {discount['discount_code']}")
        if discount.get("shopify_created"):
            print(f"  ✓ Created in Shopify (price_rule_id: {discount.get('shopify_price_rule_id')})")
        elif discount.get("shopify_error"):
            print(f"  ⚠ Shopify error: {discount['shopify_error']}")
    else:
        print("  No discount for this campaign")


def cmd_step2c(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    products = step2c_products.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP2C, en, te)
    print(f"Products selected: {out}")
    featured = products.get("featured_products", [])
    print(f"  {len(featured)} products:")
    for p in featured:
        stock = "✓" if p.get("in_stock", True) else "✗ OUT OF STOCK"
        print(f"    {stock} {p.get('title', 'Untitled')} (${p.get('price', '0')})")


def cmd_step2d(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    copy_data = step2d_copy.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP2D, en, te)
    print(f"Copy generated: {out}")
    print(f"  Subject: {copy_data.get('subject_line', '')[:60]}...")
    print(f"  Tokens filled: {len(copy_data.get('copy_by_token', {}))}")
    if copy_data.get("parse_error"):
        print("  ⚠ WARNING: JSON parse error")


def cmd_step2e(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    links_data = step2e_links.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP2E, en, te)
    print(f"Links generated: {out}")
    print(f"  Link tokens: {len(links_data.get('links_by_token', {}))}")
    print(f"  Product links: {len(links_data.get('product_links', {}))}")
    if links_data.get("parse_error"):
        print("  ⚠ WARNING: JSON parse error")


def cmd_step2f(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step2f_link_check.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP2F, en, te)
    print(f"Link check complete: {out}")
    print(f"  {result['total_ok']}/{result['total_checked']} URLs OK")


def cmd_step3(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    review = step3_cohesion.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP3, en, te)
    print(f"Cohesion review completed: {out}")
    print(f"  Cohesion score: {review.get('cohesion_score', 0)}/10")
    issues = review.get("issues_found", [])
    print(f"  Issues found: {len(issues)}")
    for issue in issues[:5]:
        severity = issue.get("severity", "unknown")
        desc = issue.get("description", "")[:60]
        print(f"    [{severity.upper()}] {desc}...")
    if len(issues) > 5:
        print(f"    ... and {len(issues) - 5} more")
    if review.get("parse_error"):
        print("  ⚠ WARNING: JSON parse error")


def cmd_step4(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step4_images.run(rd, email_num=en, total_emails=te)
    out = rd / io_util.step_filename(io_util.STEP4, en, te)
    print(f"Images step completed: {out}")
    print(f"  Raster tokens filled: {len(result.get('images_by_token', {}))}")
    print(f"  Alt strings: {len(result.get('alts_by_token', {}))}")
    errs = result.get("errors") or []
    if errs:
        print(f"  ⚠ {len(errs)} error(s):")
        for e in errs[:5]:
            print(f"    - {e}")


def cmd_step5(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step5_assembly.run(rd, skip_upload=args.skip_upload, email_num=en, total_emails=te)
    print(f"HTML assembly completed: {result['email_final_path']}")
    print(f"  Preview (local): {result['email_preview_path']}")
    if not args.skip_upload:
        uploaded = result.get("uploaded_images") or []
        print(f"  Uploaded {len(uploaded)} images to Klaviyo CDN")
    missing = result.get("missing_tokens") or []
    if missing:
        print(f"  ⚠ {len(missing)} tokens still unsubstituted:")
        for m in missing[:10]:
            print(f"    - {m}")


def cmd_step6(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step6_template.run(rd, template_name_override=args.name or "", email_num=en, total_emails=te)
    print(f"✓ Template uploaded to Klaviyo: {result['template_name']}")
    print(f"  Template ID: {result['template_id']}")
    print(f"  Edit in Klaviyo: {result['web_url']}")
    print(f"\nNext: Open the URL above to preview, test, and schedule your campaign.")


def cmd_step7(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step7_review.run(rd, email_num=en, total_emails=te)
    print(f"Visual review completed: {result.get('screenshot_path', '')}")
    print(f"  Overall score: {result.get('overall_score', 0)}/10")
    print(f"  First impression: {result.get('first_impression', '')[:80]}")
    recs = result.get("recommendations", [])
    if recs:
        print(f"  Recommendations ({len(recs)}):")
        for r in recs[:5]:
            print(f"    - {str(r)[:80]}")
    if result.get("parse_error"):
        print("  ⚠ WARNING: JSON parse error")


def cmd_step7b(args: argparse.Namespace) -> None:
    rd = io_util.run_dir(args.run)
    if not rd.is_dir():
        raise SystemExit(f"Run directory not found: {rd}")
    en, te = args.email_num, args.total_emails
    result = step7b_patch.run(rd, email_num=en, total_emails=te)
    patches = result.get("patches_applied", [])
    skipped = result.get("skipped", [])
    print(f"HTML patch completed: {result.get('patched_html_path', '')}")
    print(f"  Patches applied: {len(patches)}")
    print(f"  Skipped: {len(skipped)}")
    if result.get("screenshot_path"):
        print(f"  Post-patch screenshot: {result['screenshot_path']}")
    if result.get("parse_error"):
        print("  ⚠ WARNING: JSON parse error")


def _run_email_steps(rd: Path, email_num: int, total_emails: int, template_name: str) -> dict:
    """Run all per-email steps (2A, 2C, 2D, 2E, 2F, 3, 4, 5, 6, 7, 7b) for one email."""
    label = f" (email {email_num}/{total_emails})" if total_emails > 1 else ""

    print(f"→ Step 2A: Building HTML structure{label}...")
    step2a_structure.run(rd, email_num=email_num, total_emails=total_emails)
    print("  ✓ Structure complete\n")

    print(f"→ Step 2C: Selecting products{label}...")
    products = step2c_products.run(rd, email_num=email_num, total_emails=total_emails)
    featured = products.get("featured_products", [])
    print(f"  ✓ Selected {len(featured)} products\n")

    print(f"→ Step 2D: Writing email copy{label}...")
    copy_data = step2d_copy.run(rd, email_num=email_num, total_emails=total_emails)
    print(f"  ✓ Subject: {copy_data.get('subject_line', '')[:50]}...\n")

    print(f"→ Step 2E: Generating links{label}...")
    step2e_links.run(rd, email_num=email_num, total_emails=total_emails)
    print("  ✓ Links complete\n")

    print(f"→ Step 2F: Validating links{label}...")
    step2f_link_check.run(rd, email_num=email_num, total_emails=total_emails)
    print("  ✓ All links OK\n")

    print(f"→ Step 3: Reviewing cohesion{label}...")
    review = step3_cohesion.run(rd, email_num=email_num, total_emails=total_emails)
    score = review.get("cohesion_score", 0)
    print(f"  ✓ Cohesion score: {score}/10\n")

    print(f"→ Step 4: Generating images{label}...")
    images = step4_images.run(rd, email_num=email_num, total_emails=total_emails)
    img_count = len(images.get("images_by_token", {}))
    print(f"  ✓ Generated {img_count} images\n")

    print(f"→ Step 5: Assembling HTML and uploading to Klaviyo{label}...")
    assembly = step5_assembly.run(
        rd, skip_upload=False, email_num=email_num, total_emails=total_emails
    )
    uploaded = assembly.get("uploaded_images", [])
    print(f"  ✓ Uploaded {len(uploaded)} images to Klaviyo CDN")
    print(f"  ✓ Final HTML: {assembly['email_final_path']}\n")

    print(f"→ Step 6: Creating Klaviyo template{label}...")
    template = step6_template.run(
        rd, template_name_override=template_name, email_num=email_num, total_emails=total_emails
    )
    print(f"  ✓ Template ID: {template['template_id']}")
    print(f"  ✓ Edit URL: {template['web_url']}\n")

    print(f"→ Step 7: Visual review{label}...")
    review7 = step7_review.run(rd, email_num=email_num, total_emails=total_emails)
    print(f"  ✓ Score: {review7.get('overall_score', 0)}/10")
    recs = review7.get("recommendations", [])
    print(f"  ✓ {len(recs)} recommendation(s)\n")

    print(f"→ Step 7b: Applying HTML patches{label}...")
    patch = step7b_patch.run(rd, email_num=email_num, total_emails=total_emails)
    patches = patch.get("patches_applied", [])
    print(f"  ✓ {len(patches)} patch(es) applied\n")

    return template


def cmd_pipeline(args: argparse.Namespace) -> None:
    run_id = args.run if args.run else io_util.new_run_id(args.name)
    qpath = Path(args.questionnaire).resolve() if args.questionnaire else None

    print(f"=== Email Generation Pipeline: {run_id} ===\n")

    # Init
    if not io_util.run_dir(run_id).exists():
        print("→ Initializing run directory...")
        io_util.init_run(run_id, questionnaire_path=qpath)
        print(f"  Created: {io_util.run_dir(run_id)}\n")

    rd = io_util.run_dir(run_id)

    # Read sequence length from questionnaire
    q_path = rd / "questionnaire.yaml"
    total_emails = 1
    if q_path.is_file():
        try:
            q = questionnaire.load(q_path)
            total_emails = q.get("sequence_num_emails", 1)
        except Exception:
            total_emails = 1

    seq_label = f" ({total_emails}-email sequence)" if total_emails > 1 else ""
    print(f"Sequence mode: {total_emails} email(s){seq_label}\n")

    # Step 1: Brief (runs once — generates sequence brief if total_emails > 1)
    print("→ Step 1: Generating creative brief...")
    step1_brief.run(rd)
    print("  ✓ Brief complete\n")

    # Step 2B: Discount (runs once — shared code across all emails)
    print("→ Step 2B: Processing discount strategy...")
    discount = step2b_discount.run(rd)
    if discount.get("discount_code"):
        print(f"  ✓ Discount code: {discount['discount_code']}")
    else:
        print("  ✓ No discount for this campaign")
    print()

    # Per-email steps (2A, 2C, 2D, 2E, 2F, 3, 4, 5, 6, 7, 7b)
    last_template: dict = {}
    for email_num in range(1, total_emails + 1):
        if total_emails > 1:
            print(f"{'='*50}")
            print(f"  EMAIL {email_num} OF {total_emails}")
            print(f"{'='*50}\n")
        last_template = _run_email_steps(
            rd, email_num=email_num, total_emails=total_emails,
            template_name=args.template_name or "",
        )

    print("=== Pipeline Complete ===")
    print(f"Run ID: {run_id}")
    if total_emails > 1:
        print(f"Generated {total_emails} emails in sequence.")
        print("Klaviyo templates:")
        for n in range(1, total_emails + 1):
            tf = rd / f"step6_template_email_{n}.json"
            if tf.is_file():
                t = io_util.read_json(tf)
                print(f"  Email {n}: {t.get('web_url', '(see run dir)')}")
    else:
        print(f"Klaviyo template: {last_template.get('web_url', '')}")
        print("\nOpen the URL above to preview, test, and schedule your campaign in Klaviyo.")


def main() -> None:
    p = argparse.ArgumentParser(description="Yay's Email Generator v1")
    sub = p.add_subparsers(dest="command", required=True)

    ideas = sub.add_parser("ideas", help="Generate email campaign ideas from customer reviews")
    ideas.add_argument(
        "--product-focus",
        type=str,
        default=None,
        choices=["beef_crisps", "pork_crisps", "crispy_beef_bits", "all"],
        help="Filter ideas to a specific product line (default: all)",
    )
    ideas.add_argument(
        "--output", "-o", type=str, default=None, help="Save ideas as JSON to this path"
    )
    ideas.set_defaults(func=cmd_ideas)

    ba = sub.add_parser("brand-analysis", help="Analyse website screenshots → brand/identity_text/visual_brand_analysis.txt")
    ba.add_argument("--inspo-dir", type=str, default=None, help=f"Folder of screenshots (default: brand/website/)")
    ba.add_argument("--output", "-o", type=str, default=None, help="Output .txt path (default: brand/identity_text/visual_brand_analysis.txt)")
    ba.add_argument("--model", type=str, default=None, help="Gemini model override (default: gemini-2.5-pro)")
    ba.set_defaults(func=cmd_brand_analysis)

    nq = sub.add_parser("new-questionnaire", help="Copy template to a YAML file")
    nq.add_argument(
        "--output",
        "-o",
        default="questionnaire.yaml",
        help="Destination path (default: ./questionnaire.yaml)",
    )
    nq.set_defaults(func=cmd_new_questionnaire)

    ir = sub.add_parser("init-run", help="Create output/<run_id>/ with meta.json")
    ir.add_argument("--name", type=str, default=None, help="Run id (default: timestamp)")
    ir.add_argument(
        "--questionnaire",
        type=str,
        default=None,
        help="Path to filled questionnaire YAML to copy into the run",
    )
    ir.set_defaults(func=cmd_init_run)

    s1 = sub.add_parser("step1", help="Generate email brief (Step 1)")
    s1.add_argument("--run", type=str, required=True, help="Run ID")
    s1.set_defaults(func=cmd_step1)

    def _add_seq_args(parser: argparse.ArgumentParser) -> None:
        """Add --email-num and --total-emails flags to per-email step parsers."""
        parser.add_argument(
            "--email-num", type=int, default=1,
            dest="email_num",
            help="Email index in sequence (default: 1; single email)"
        )
        parser.add_argument(
            "--total-emails", type=int, default=1,
            dest="total_emails",
            help="Total number of emails in sequence (default: 1)"
        )

    s2a = sub.add_parser("step2a", help="Generate HTML structure (Step 2A)")
    s2a.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s2a)
    s2a.set_defaults(func=cmd_step2a)

    s2b = sub.add_parser("step2b", help="Generate discount strategy (Step 2B)")
    s2b.add_argument("--run", type=str, required=True, help="Run ID")
    s2b.set_defaults(func=cmd_step2b)

    s2c = sub.add_parser("step2c", help="Select products (Step 2C)")
    s2c.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s2c)
    s2c.set_defaults(func=cmd_step2c)

    s2d = sub.add_parser("step2d", help="Generate copy (Step 2D)")
    s2d.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s2d)
    s2d.set_defaults(func=cmd_step2d)

    s2e = sub.add_parser("step2e", help="Generate links (Step 2E)")
    s2e.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s2e)
    s2e.set_defaults(func=cmd_step2e)

    s2f = sub.add_parser("step2f", help="HTTP-validate all links (Step 2F)")
    s2f.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s2f)
    s2f.set_defaults(func=cmd_step2f)

    s3 = sub.add_parser("step3", help="Cohesion review (Step 3)")
    s3.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s3)
    s3.set_defaults(func=cmd_step3)

    s4 = sub.add_parser("step4", help="Image generation (Step 4)")
    s4.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s4)
    s4.set_defaults(func=cmd_step4)

    s5 = sub.add_parser("step5", help="HTML assembly + Klaviyo upload (Step 5)")
    s5.add_argument("--run", type=str, required=True, help="Run ID")
    s5.add_argument("--skip-upload", action="store_true", help="Skip Klaviyo image uploads (local preview only)")
    _add_seq_args(s5)
    s5.set_defaults(func=cmd_step5)

    s6 = sub.add_parser("step6", help="Upload template to Klaviyo (Step 6)")
    s6.add_argument("--run", type=str, required=True, help="Run ID")
    s6.add_argument("--name", type=str, default="", help="Override template name")
    _add_seq_args(s6)
    s6.set_defaults(func=cmd_step6)

    s7 = sub.add_parser("step7", help="Visual review — screenshot + Gemini critique (Step 7)")
    s7.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s7)
    s7.set_defaults(func=cmd_step7)

    s7b = sub.add_parser("step7b", help="HTML patch — apply fixes from Step 7 review (Step 7b)")
    s7b.add_argument("--run", type=str, required=True, help="Run ID")
    _add_seq_args(s7b)
    s7b.set_defaults(func=cmd_step7b)

    pipeline = sub.add_parser("pipeline", help="Run full pipeline (Steps 1-7b)")
    pipeline.add_argument("--run", type=str, default="", help="Existing run ID (or creates new)")
    pipeline.add_argument("--name", type=str, default=None, help="New run name")
    pipeline.add_argument("--questionnaire", type=str, default=None, help="Path to questionnaire YAML")
    pipeline.add_argument("--template-name", type=str, default="", help="Override Klaviyo template name")
    pipeline.set_defaults(func=cmd_pipeline)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
