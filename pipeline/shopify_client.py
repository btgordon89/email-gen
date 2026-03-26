"""Shopify Admin API client for product data, discounts, and links."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from . import config


def _headers() -> Dict[str, str]:
    return {
        "X-Shopify-Access-Token": config.shopify_admin_api_token(),
        "Content-Type": "application/json",
    }


def _api_base() -> str:
    shop = config.shopify_shop_url()
    return f"https://{shop}/admin/api/2024-01"


def get_products(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch active products from Shopify."""
    url = f"{_api_base()}/products.json?limit={limit}&status=active"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    products = resp.json().get("products", [])
    
    # Enrich with inventory data
    for product in products:
        for variant in product.get("variants", []):
            inventory_item_id = variant.get("inventory_item_id")
            if inventory_item_id:
                try:
                    inv_url = f"{_api_base()}/inventory_levels.json?inventory_item_ids={inventory_item_id}"
                    inv_resp = requests.get(inv_url, headers=_headers(), timeout=10)
                    inv_resp.raise_for_status()
                    levels = inv_resp.json().get("inventory_levels", [])
                    # Sum inventory across all locations
                    total_inventory = sum(level.get("available", 0) for level in levels)
                    variant["inventory_quantity"] = total_inventory
                    variant["in_stock"] = total_inventory > 0
                except Exception:
                    # If inventory check fails, assume in stock
                    variant["inventory_quantity"] = None
                    variant["in_stock"] = True
            else:
                variant["inventory_quantity"] = None
                variant["in_stock"] = True
    
    return products


def get_product_by_handle(handle: str) -> Optional[Dict[str, Any]]:
    """Fetch a single product by handle."""
    url = f"{_api_base()}/products.json?handle={handle}"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    products = resp.json().get("products", [])
    return products[0] if products else None


def get_collections() -> List[Dict[str, Any]]:
    """Fetch all collections (custom + smart)."""
    collections = []
    for ctype in ["custom_collections", "smart_collections"]:
        url = f"{_api_base()}/{ctype}.json"
        resp = requests.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        collections.extend(resp.json().get(ctype, []))
    return collections


def create_price_rule(price_rule_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a Shopify price rule."""
    url = f"{_api_base()}/price_rules.json"
    payload = {"price_rule": price_rule_data}
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()["price_rule"]


def create_discount_code(price_rule_id: int, code: str) -> Dict[str, Any]:
    """Create a discount code under a price rule."""
    url = f"{_api_base()}/price_rules/{price_rule_id}/discount_codes.json"
    payload = {"discount_code": {"code": code}}
    resp = requests.post(url, json=payload, headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()["discount_code"]


def get_shop_url() -> str:
    """Return the public storefront URL."""
    return "https://snackyays.com"
