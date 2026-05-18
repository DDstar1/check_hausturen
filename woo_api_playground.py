"""
WooCommerce REST API playground — run this standalone to explore the API.
Nothing in this file touches the main app.

Requirements:
    pip install requests

Docs: https://woocommerce.github.io/woocommerce-rest-api-docs/
"""

import json
import requests
from requests.auth import HTTPBasicAuth

# ── CONFIG ────────────────────────────────────────────────────────────────────
STORE_URL   = "https://innentuerenshop.paultec.de/"   # no trailing slash
CONSUMER_KEY    = "ck_ff98fa87702242818e6aa6747b07cfa59419c453"
CONSUMER_SECRET = "cs_c16a6beae2d5de42e65aaea4b711c8e7a7b8d679"
# ─────────────────────────────────────────────────────────────────────────────

auth = HTTPBasicAuth(CONSUMER_KEY, CONSUMER_SECRET)
BASE = f"{STORE_URL}/wp-json/wc/v3"


def _get(endpoint: str, params: dict = None):
    url = f"{BASE}/{endpoint}"
    r = requests.get(url, auth=auth, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def _put(endpoint: str, data: dict):
    url = f"{BASE}/{endpoint}"
    r = requests.put(url, auth=auth, json=data, timeout=15)
    r.raise_for_status()
    return r.json()


def update_product(product_id: int, **fields) -> dict:
    """
    Update any top-level fields on a product.

    Common fields:
        regular_price   "49.99"
        sale_price      "39.99"  (empty string "" to clear it)
        status          "publish" | "draft" | "private"
        name            "New product name"
        attributes      list of attribute dicts (see set_product_attributes)

    Returns the updated product dict.
    """
    return _put(f"products/{product_id}", fields)


def update_variation(product_id: int, variation_id: int, **fields) -> dict:
    """
    Update fields on a single variation.

    Common fields:
        regular_price   "49.99"
        sale_price      "39.99"
        status          "publish" | "private"
        attributes      [{"name": "Farbe", "option": "weiß"}, ...]

    Returns the updated variation dict.
    """
    return _put(f"products/{product_id}/variations/{variation_id}", fields)


def set_product_price(product_id: int, regular_price: str, sale_price: str = "") -> dict:
    """Shortcut to set the price on a simple product."""
    return update_product(product_id, regular_price=regular_price, sale_price=sale_price)


def set_variation_price(product_id: int, variation_id: int, regular_price: str, sale_price: str = "") -> dict:
    """Shortcut to set the price on a specific variation."""
    return update_variation(product_id, variation_id, regular_price=regular_price, sale_price=sale_price)


def set_product_attributes(product_id: int, attributes: list) -> dict:
    """
    Set the attribute options visible on the product page (not per-variation).

    attributes format:
        [
            {"name": "Farbe",  "options": ["weiß", "anthrazit"], "visible": True, "variation": True},
            {"name": "Breite", "options": ["900", "1000"],       "visible": True, "variation": True},
        ]
    """
    return update_product(product_id, attributes=attributes)


def get_product(product_id: int) -> dict:
    """Fetch a single product by ID."""
    return _get(f"products/{product_id}")


def get_product_by_sku(sku: str) -> dict | None:
    """
    Fetch a product by its SKU.
    Returns the product dict, or None if not found.
    WooCommerce SKUs are unique, so this always returns at most one result.
    """
    results = _get("products", {"sku": sku})
    return results[0] if results else None


def get_product_by_slug(slug: str) -> dict | None:
    """
    Fetch a product by its URL slug (the part after the last slash in the permalink).
    e.g. permalink https://store.com/product/meine-tuer/ → slug "meine-tuer"
    """
    results = _get("products", {"slug": slug})
    return results[0] if results else None


def get_product_by_url(permalink: str) -> dict | None:
    """
    Fetch a product by its full permalink URL.
    Extracts the slug automatically, so you can paste the URL directly.
    """
    slug = permalink.rstrip("/").rsplit("/", 1)[-1]
    return get_product_by_slug(slug)


def get_product_variations(product_id: int) -> list:
    """Fetch all variations of a variable product."""
    results, page = [], 1
    while True:
        batch = _get(f"products/{product_id}/variations", {"per_page": 100, "page": page})
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def get_variation(product_id: int, variation_id: int) -> dict:
    """Fetch a single variation."""
    return _get(f"products/{product_id}/variations/{variation_id}")


def search_products(query: str, per_page: int = 10) -> list:
    """Search products by name."""
    return _get("products", {"search": query, "per_page": per_page})


def list_products(per_page: int = 10, page: int = 1, **filters) -> list:
    """List products with optional filters (status, category, type, etc.)."""
    return _get("products", {"per_page": per_page, "page": page, **filters})


def list_categories(per_page: int = 100, search: str = None) -> list:
    """List all product categories. Pass search= to filter by name."""
    params = {"per_page": per_page}
    if search:
        params["search"] = search
    return _get("products/categories", params)


def get_products_in_category(category_id: int) -> list:
    """Fetch ALL products in a category (auto-paginates)."""
    results, page = [], 1
    while True:
        batch = _get("products", {"category": category_id, "per_page": 100, "page": page})
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return results


def pp(data):
    """Pretty-print JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


def save_json(data, filename: str):
    """Write data to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved → {filename}")


# ── HELPERS TO PULL USEFUL FIELDS ────────────────────────────────────────────

def is_ab_price_showing(p: dict) -> bool:
    """
    Returns True if the product is displaying an 'Ab:' (from-price) banner.
    Checks price_html from the raw product dict — no extra request needed.
    """
    return "Ab:" in p.get("price_html", "") or "Ab: " in p.get("price_html", "")


def product_summary(p: dict) -> dict:
    """Extract the fields most useful for validation."""
    return {
        "id":              p.get("id"),
        "name":            p.get("name"),
        "type":            p.get("type"),
        "status":          p.get("status"),
        "permalink":       p.get("permalink"),
        "price":           p.get("price"),
        "regular_price":   p.get("regular_price"),
        "sale_price":      p.get("sale_price"),
        "purchasable":     p.get("purchasable"),   # False = button disabled
        "on_sale":         p.get("on_sale"),
        "ab_price_showing":is_ab_price_showing(p),
        "categories":      [c["name"] for c in p.get("categories", [])],
        "attributes":      [
            {"name": a["name"], "options": a.get("options", [])}
            for a in p.get("attributes", [])
        ],
        "variations":      p.get("variations", []),
    }


def variation_summary(v: dict) -> dict:
    return {
        "id":            v.get("id"),
        "price":         v.get("price"),
        "regular_price": v.get("regular_price"),
        "sale_price":    v.get("sale_price"),
        "purchasable":   v.get("purchasable"),
        "on_sale":       v.get("on_sale"),
        "attributes":    {a["name"]: a["option"] for a in v.get("attributes", [])},
    }


# ── QUICK DEMO ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Change the product ID below and run:  python woo_api_playground.py

    PRODUCT_ID = 24135  # ← put a real product ID here

    print("=== Product ===")
    product = get_product(PRODUCT_ID)
    pp(product_summary(product))
    save_json(product, f"product_{PRODUCT_ID}.json")

    if product.get("type") == "variable":
        print(f"\n=== Variations ({len(product['variations'])} total) ===")
        variations = get_product_variations(PRODUCT_ID)
        for v in variations[:5]:   # print first 5
            pp(variation_summary(v))

    # Uncomment to try other helpers:
    # pp(search_products("haustur"))
    # pp(list_products(per_page=5, status="publish"))

    # --- Category helpers ---
    # List all categories (name + id):
    # for cat in list_categories():
    #     print(cat["id"], cat["name"])

    # Search categories by name:
    # pp(list_categories(search="haustuer"))

    # Get every product in a category (auto-paginates):
    # CATEGORY_ID = 123
    # products = get_products_in_category(CATEGORY_ID)
    # print(f"{len(products)} products in category {CATEGORY_ID}")
    # for p in products:
    #     pp(product_summary(p))

    # --- Update helpers (these write to the store!) ---

    # Set price on a simple product:
    # pp(set_product_price(PRODUCT_ID, regular_price="499.99"))
    # pp(set_product_price(PRODUCT_ID, regular_price="499.99", sale_price="399.99"))

    # Clear sale price:
    # pp(set_product_price(PRODUCT_ID, regular_price="499.99", sale_price=""))

    # Set price on a specific variation:
    # VARIATION_ID = 99999
    # pp(set_variation_price(PRODUCT_ID, VARIATION_ID, regular_price="299.99"))

    # Update variation attributes (pick a specific combination):
    # pp(update_variation(PRODUCT_ID, VARIATION_ID, attributes=[
    #     {"name": "Farbe",  "option": "weiß"},
    #     {"name": "Breite", "option": "900"},
    # ]))

    # Update product-level attribute options (what shows in the dropdown):
    # pp(set_product_attributes(PRODUCT_ID, [
    #     {"name": "Farbe",  "options": ["weiß", "anthrazit"], "visible": True, "variation": True},
    #     {"name": "Breite", "options": ["900", "1000"],       "visible": True, "variation": True},
    # ]))

    # Any other field — use update_product directly:
    # pp(update_product(PRODUCT_ID, status="draft"))
    # pp(update_product(PRODUCT_ID, name="Neue Bezeichnung"))
