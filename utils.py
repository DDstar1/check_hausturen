"""Constants and helper functions shared across the app."""

import os
import re
import sys
from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────
# When frozen by PyInstaller the bundle root is sys._MEIPASS; in dev it sits
# next to this file.
_env_path = os.path.join(
    sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__)),
    ".env",
)
load_dotenv(_env_path)


def _load_stores() -> dict:
    """
    Build the WOO_STORES dict from .env entries.

    Every store needs three vars using a shared prefix:
        PREFIX_LABEL   — display name shown in the UI
        PREFIX_URL     — store base URL
        PREFIX_KEY     — WooCommerce consumer key
        PREFIX_SECRET  — WooCommerce consumer secret

    Add a new store by adding another PREFIX_* block to .env — no code change needed.
    """
    prefixes = sorted({k[:-6] for k in os.environ if k.endswith("_LABEL")})
    stores = {}
    for p in prefixes:
        label  = os.environ.get(f"{p}_LABEL", p)
        url    = os.environ.get(f"{p}_URL", "")
        key    = os.environ.get(f"{p}_KEY", "")
        secret = os.environ.get(f"{p}_SECRET", "")
        if url and key and secret:
            stores[label] = {"url": url, "consumer_key": key, "consumer_secret": secret}
    return stores


WOO_STORES = _load_stores()
# ─────────────────────────────────────────────────────────────────────────────

ATTR_COLUMN_MAP = {
    "FÜLLUNG":                    "rodenberg-fuellung",
    "AUSFÜHRUNG":                 "rodenberg-ausfuhrung",
    "BREITE":                     "rodenberg-breite",
    "HÖHE":                       "rodenberg-hoehe",
    "ELEMENT":                    "rodenberg-element",
    "VERGLASUNG":                 "rodenberg-verglasung",
    "LISENEN":                    "rodenberg-lisenen",
    "FARBE":                      "rodenberg-farbe",
    "Seitenteil RC 2/3":          "rodenberg-seitenteil-breite",
    "Rodenberg Füllung":          "rodenberg-fuellung",
    "Rodenberg Fülllung":         "rodenberg-fuellung",
    "Rodenberg Ausführung":       "rodenberg-ausfuhrung",
    "Rodenberg Ausfuhrung":       "rodenberg-ausfuhrung",
    "Rodenberg Breite":           "rodenberg-breite",
    "Rodenberg Höhe":             "rodenberg-hoehe",
    "Rodenberg Element":          "rodenberg-element",
    "Rodenberg Verglasung":       "rodenberg-verglasung",
    "Rodenberg Lisenen":          "rodenberg-lisenen",
    "Rodenberg Farbe":            "rodenberg-farbe",
    "Rodenberg Seitenteil Breite":"rodenberg-seitenteil-breite",
}

SLUG_ALIASES = {
    "turblatt": "tuerfuellung",
    "aufsatzfuellung-seitenteil": "aufsatzfuellung",
}

SPECIAL_ROLES = {
    "name":     lambda h: h.upper() in ("PRODUCTS", "PRODUCT", "NAME", "PRODUKT"),
    "category": lambda h: h.upper() in ("KATEGORY", "CATEGORY", "KATEGORIE"),
}

RESULT_HEADERS = [
    "Product Name", "Category", "Material", "Product ID",
    "Purchasable", "Has Form",
    "AB Price Showing", "Website Price", "Excel AB Price", "AB Match",
    "Excel Base Price", "Base Match",
    "Vars Match", "Mismatch", "URL",
]


def find_id_columns(headers: list) -> list:
    """
    Detect product ID columns and pair them with their price columns.

    A column is an ID column if its lowercased name contains '_id' or equals 'id'
    and does not contain 'price'.  The prefix is used to find paired price columns.

    Returns a list of dicts:
        {"id_col": str, "prefix": str, "base_price_col": str|None, "ab_price_col": str|None}
    """
    lower = {h: h.lower() for h in headers}
    result = []
    for h in headers:
        hl = lower[h]
        if "price" in hl:
            continue
        if not ("_id" in hl or hl == "id" or hl.startswith("id_")):
            continue
        prefix = re.sub(r"[_-]?id$", "", hl).rstrip("_-")
        base_price_col = next(
            (x for x in headers if lower[x] == f"{prefix}_base_price"), None)
        ab_price_col = next(
            (x for x in headers if lower[x] == f"{prefix}_ab_price"), None)
        result.append({
            "id_col":        h,
            "prefix":        prefix,
            "base_price_col": base_price_col,
            "ab_price_col":   ab_price_col,
        })
    return result


def excel_value_to_slug(value):
    if not value or str(value).strip() in ("", "None", "-", "Nil"):
        return None
    value = str(value).strip()
    if re.match(r"Group\s+\d+", value, re.IGNORECASE):
        return "premium-group-" + re.search(r"\d+", value).group()
    if re.match(r"Premium\s+\d+", value, re.IGNORECASE):
        return "premium-" + re.search(r"\d+", value).group()
    slug = value.lower()
    for old, new in [("ü","ue"),("ö","oe"),("ä","ae"),("ß","ss"),(" & ","-"),("&","")]:
        slug = slug.replace(old, new)
    slug = re.sub(r"[^\w-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    for a_from, a_to in SLUG_ALIASES.items():
        slug = slug.replace(a_from, a_to)
    return slug


def has_tm_form(product: dict) -> bool:
    """
    Returns True if the product has a custom TM Extra Product Options form.

    WooCommerce always creates a 'variations' element in tmfbuilder even when
    there is no custom form.  A real form exists only when element_type contains
    entries *other* than 'variations'.
    """
    for m in product.get("meta_data", []):
        if m.get("key") == "tm_meta":
            val = m.get("value", {})
            if isinstance(val, dict):
                elements = val.get("tmfbuilder", {}).get("element_type", [])
                return any(e != "variations" for e in elements)
    return False


def is_ab_price_showing(product: dict) -> bool:
    return "Ab:" in product.get("price_html", "") or "Ab: " in product.get("price_html", "")


def extract_ab_price(product: dict) -> str:
    """
    Extract the numeric price string from price_html when an 'Ab:' banner is showing.
    Returns a string like '886,03' that parse_price() can handle.
    Falls back to the product's 'price' field if parsing fails.
    """
    if not is_ab_price_showing(product):
        return ""
    html = product.get("price_html", "")
    # Strip all HTML tags
    text = re.sub(r"<[^>]+>", "", html)
    # Remove HTML entities and currency symbols
    for tok in ("&euro;", "&amp;", "€", "Ab:", "Ab :", "\xa0"):
        text = text.replace(tok, " ")
    # Find the first number (handles '886,03' and '1.234,56' formats)
    match = re.search(r"\d[\d.,]*", text.strip())
    if match:
        return match.group()
    return product.get("price", "")


def parse_price(s):
    s = re.sub(r"[^\d,.]", "", str(s))
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def prices_match(excel_price, website_price):
    a, b = parse_price(excel_price), parse_price(website_price)
    if a is None or b is None:
        return "N/A"
    return abs(a - b) < 0.05
