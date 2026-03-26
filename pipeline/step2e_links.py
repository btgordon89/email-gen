"""Step 2E: Link Agent — generate all URLs for CTAs and products."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from . import base_step, config, gemini_text, io_util, shopify_client, validators

# Social link token names as they appear in the token manifest
_SOCIAL_TOKENS = {
    "{{instagram_link}}": config.brand_instagram_url,
    "{{tiktok_link}}": config.brand_tiktok_url,
    "{{facebook_link}}": config.brand_facebook_url,
}


class Step2eLinks(base_step.BaseStep):
    """Generate all URLs for CTAs and products."""
    
    step_id = "step2e_links"
    output_filename = io_util.STEP2E
    model_fn = staticmethod(config.links_model)
    default_schema = {
        "links_by_token": {},
        "product_links": {},
        "collection_links": {},
        "unsubscribe_link": "{{unsubscribe_url}}",
        "preferences_link": "{{preferences_url}}",
        "resolution_notes": "",
    }
    
    def load_inputs(self, run_dir: Path) -> Dict[str, Any]:
        """Load brief, structure, discount, products, Shopify collections, and brand social URLs."""
        full_brief = io_util.read_json(run_dir / io_util.STEP1)
        brief = self._brief_for_email(full_brief)
        structure = io_util.read_json(self._step_path(run_dir, io_util.STEP2A))
        discount = io_util.read_json(self._step_path(run_dir, io_util.STEP2B, per_email=False))
        products = io_util.read_json(self._step_path(run_dir, io_util.STEP2C))

        # Load brand social URLs from config — never infer these
        social_urls = {token: fn() for token, fn in _SOCIAL_TOKENS.items()}
        
        # Fetch collections from Shopify
        try:
            collections = shopify_client.get_collections()
            
            # Filter out internal/test collections
            excluded_keywords = [
                "grovery",
                "reelup",
                "do-not-delete",
                "do-not-edit",
                "test",
                "draft",
            ]
            
            filtered_collections = []
            for c in collections:
                handle = c.get("handle", "").lower()
                if not any(keyword in handle for keyword in excluded_keywords):
                    filtered_collections.append(c)
            
            collections = filtered_collections
        except Exception as e:
            collections = []
            # Non-fatal: can still generate links without collections
        
        return {
            "brief": brief,
            "structure": structure,
            "discount": discount,
            "products": products,
            "collections": collections,
            "social_urls": social_urls,
        }
    
    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """Build link generation prompt."""
        brief = inputs["brief"]
        structure = inputs["structure"]
        discount = inputs["discount"]
        products = inputs["products"]
        collections = inputs["collections"]
        
        link_tokens = [
            t for t in structure.get("token_manifest", [])
            if t.get("source_agent") == "link"
        ]
        link_tokens_text = json.dumps(link_tokens, indent=2)

        cta_reqs = brief.get("cta_requirements", [])
        cta_text = json.dumps(cta_reqs, indent=2)

        featured = products.get("featured_products", [])
        products_text = "\n".join([
            f"- {p['title']}: handle={p['handle']}"
            for p in featured
        ])

        collections_text = "\n".join([
            f"- {c.get('title', '')}: handle={c.get('handle', '')}"
            for c in collections[:20]
        ])

        discount_code = discount.get("discount_code")
        discount_text = f"Discount code: {discount_code}" if discount_code else "No discount code"

        social_urls = inputs.get("social_urls", {})
        social_lines = [
            f"  {token}: {url}" for token, url in social_urls.items() if url
        ]
        social_text = (
            "BRAND SOCIAL URLS (use these exact values — do not infer or modify):\n"
            + "\n".join(social_lines)
            if social_lines
            else "BRAND SOCIAL URLS: not configured — leave tokens as-is if unsure"
        )

        return f"""Generate all URLs for this email campaign.

STOREFRONT BASE: https://snackyays.com

LINK TOKENS TO FILL:
{link_tokens_text}

CTA REQUIREMENTS (from brief):
{cta_text}

FEATURED PRODUCTS (use these handles):
{products_text}

AVAILABLE COLLECTIONS (from Shopify):
{collections_text}

{discount_text}

{social_text}

Map each link token to the correct URL. Append ?discount={discount_code} to all shopping links if a code exists."""
    
    def validate(self, output: Dict[str, Any], inputs: Dict[str, Any]) -> List[str]:
        """Validate that all required link tokens are filled and social URLs match config."""
        warnings = validators.validate_links_completeness(output, inputs["structure"])

        social_urls = inputs.get("social_urls", {})
        links_by_token = output.get("links_by_token", {})
        for token, url in social_urls.items():
            if not url:
                continue
            actual = links_by_token.get(token, "")
            if actual and actual != url:
                warnings.append(
                    f"Social link mismatch for {token}: LLM output '{actual}' differs from "
                    f"config '{url}' — config value will be used"
                )

        return warnings

    def run(self, run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
        """Run step, then enforce brand social URLs from config regardless of LLM output."""
        result = super().run(run_dir, email_num=email_num, total_emails=total_emails)

        social_urls = {token: fn() for token, fn in _SOCIAL_TOKENS.items()}
        patched = False
        for token, url in social_urls.items():
            if url and token in result.get("links_by_token", {}):
                result["links_by_token"][token] = url
                patched = True

        if patched:
            output_file = io_util.step_filename(self.output_filename, email_num, total_emails)
            io_util.write_json(run_dir / output_file, result)

        return result


# Singleton instance for backward compatibility
_instance = Step2eLinks()


def run(run_dir: Path, email_num: int = 1, total_emails: int = 1) -> Dict[str, Any]:
    """Generate all URLs for CTAs and products."""
    return _instance.run(run_dir, email_num=email_num, total_emails=total_emails)

