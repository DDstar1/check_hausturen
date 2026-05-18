"""ApiWorker — validates products via WooCommerce REST API in a background QThread."""

import html as _html

from PySide6.QtCore import QThread, Signal
import requests
from requests.auth import HTTPBasicAuth

from utils import has_tm_form, is_ab_price_showing, extract_ab_price, prices_match


def _api_get(endpoint: str, store: dict, params: dict = None) -> dict | list:
    auth = HTTPBasicAuth(store["consumer_key"], store["consumer_secret"])
    base = f"{store['url'].rstrip('/')}/wp-json/wc/v3"
    r = requests.get(f"{base}/{endpoint}", auth=auth, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


class ApiWorker(QThread):
    log       = Signal(str)
    progress  = Signal(int, int)
    row_ready = Signal(list)
    finished  = Signal()

    def __init__(self, excel_rows: list, custom_checks: list, store: dict, terms_cache: dict = None):
        super().__init__()
        self.excel_rows    = excel_rows
        self.custom_checks = custom_checks
        self.store         = store
        self._stop         = False
        self._terms_cache  = terms_cache or {}

    def stop(self):
        self._stop = True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.log.emit(f"Using pre-fetched attribute cache ({len(self._terms_cache)} attribute(s)).\n")
        total = sum(len(r["materials"]) for r in self.excel_rows)
        count = 0
        for row in self.excel_rows:
            if self._stop:
                self.log.emit("[STOPPED]")
                break
            for mat in row["materials"]:
                if self._stop:
                    break
                count += 1
                self._validate(row, mat, count, total)
        self.log.emit("\nAll products checked.")
        self.finished.emit()

    # ------------------------------------------------------------------
    # Per-product validation
    # ------------------------------------------------------------------

    def _validate(self, row: dict, mat: dict, index: int, total: int):
        pid      = mat["product_id"]
        material = mat["prefix"]
        name     = row.get("name", "")
        category = row.get("category", "")

        self.log.emit(f"\n{'='*55}")
        self.log.emit(f"[{index}/{total}] {material.upper()} — product ID {pid}")

        try:
            product = _api_get(f"products/{pid}", self.store)
        except Exception as e:
            self.log.emit(f"  [ERROR] API fetch failed: {e}")
            self.row_ready.emit([
                name, category, material, pid,
                "ERROR", "ERROR",
                "ERROR", "", mat.get("ab_price", ""), "N/A",
                mat.get("base_price", ""), "N/A",
                "ERROR", str(e), "",
            ])
            self.progress.emit(index, total)
            return

        # ── Purchasable: default_attributes count must equal attributes count ──
        all_attrs     = product.get("attributes", [])
        default_attrs = product.get("default_attributes", [])
        purchasable   = len(all_attrs) > 0 and len(default_attrs) == len(all_attrs)
        form          = has_tm_form(product)
        self.log.emit(
            f"  Attributes: {len(all_attrs)}  Default attrs: {len(default_attrs)}"
            f"  → purchasable={purchasable}  has_form={form}"
        )

        # ── AB price ──────────────────────────────────────────────────────────
        ab_showing     = is_ab_price_showing(product)
        website_ab     = extract_ab_price(product)   # parsed from price_html
        website_price  = product.get("price", "")    # fallback / base price
        excel_ab       = mat.get("ab_price", "")
        excel_base     = mat.get("base_price", "")
        ab_match       = prices_match(excel_ab, website_ab)   if ab_showing     else "N/A"
        base_match     = prices_match(excel_base, website_price) if not ab_showing else "N/A"
        self.log.emit(
            f"  AB showing={ab_showing}  Website AB={website_ab!r}  Website price={website_price!r}"
            f"  Excel AB={excel_ab!r}  Excel base={excel_base!r}"
        )

        # ── Variable attribute check ──────────────────────────────────────────
        # Build slug→display-name map from the pre-fetched cache
        slug_to_name = {}
        for attr in all_attrs:
            attr_id = attr.get("id")
            if attr_id and attr_id in self._terms_cache:
                slug_to_name.update(self._terms_cache[attr_id])

        attr_values  = dict(row.get("attr_values", {}))
        absent_attrs = set(row.get("absent_attrs", set()))
        for slug, val in self.custom_checks:
            attr_values[slug] = val

        vars_match, mismatch = self._check_default_attrs(
            default_attrs, all_attrs, attr_values, absent_attrs, slug_to_name
        )
        self.log.emit(f"  Vars match={vars_match}  mismatch={mismatch!r}")

        displayed_price = website_ab if ab_showing else website_price
        self.row_ready.emit([
            name, category, material, pid,
            str(purchasable), str(form),
            str(ab_showing), displayed_price, excel_ab, str(ab_match),
            excel_base, str(base_match),
            str(vars_match), mismatch,
            product.get("permalink", ""),
        ])
        self.progress.emit(index, total)

    # ------------------------------------------------------------------
    # Attribute comparison helpers
    # ------------------------------------------------------------------

    def _check_default_attrs(
        self,
        default_attrs: list,
        all_attrs: list,
        attr_values: dict,
        absent_attrs: set,
        slug_to_name: dict,
    ) -> tuple[bool, str]:
        if not attr_values and not absent_attrs:
            self.log.emit("  No attribute checks configured")
            return True, ""

        # Build lookup: api_attr_name_lower → resolved display name
        api_lookup = {}
        for da in default_attrs:
            option_slug = da.get("option", "")
            display     = slug_to_name.get(option_slug, _html.unescape(option_slug))
            api_lookup[da.get("name", "").lower()] = display
            self.log.emit(f"    API default: {da.get('name')!r} = {display!r}")

        issues = []
        match  = True

        # attr_values keys are the original Excel column names (e.g. "Rodenberg Füllung")
        for col_name, excel_val in attr_values.items():
            found_key = self._find_attr_by_name(col_name, api_lookup)
            if found_key is None:
                self.log.emit(f"    '{col_name}': NOT in default_attributes")
                issues.append(f"'{col_name}': not set as default")
                match = False
                continue
            actual = api_lookup[found_key]
            ok     = actual.lower() == excel_val.lower()
            self.log.emit(
                f"    '{col_name}': expected={excel_val!r} actual={actual!r}"
                f" => {'OK' if ok else 'MISMATCH'}"
            )
            if not ok:
                match = False
                issues.append(f"'{col_name}': expected '{excel_val}', got '{actual}'")

        for col_name in absent_attrs:
            found_key = self._find_attr_by_name(col_name, api_lookup)
            if found_key:
                self.log.emit(f"    '{col_name}': expected ABSENT but IS set => MISMATCH")
                match = False
                issues.append(f"'{col_name}': should be absent but is set")
            else:
                self.log.emit(f"    '{col_name}': expected ABSENT, confirmed absent => OK")

        return match, " | ".join(issues)

    @staticmethod
    def _find_attr_by_name(col_name: str, api_lookup: dict) -> str | None:
        """Find the API attribute entry whose name appears inside the Excel column name.

        e.g. col_name='Rodenberg Füllung', api_lookup has key 'füllung' → matches.
        """
        col_lower = col_name.lower()
        # Exact match first
        if col_lower in api_lookup:
            return col_lower
        # Substring: API name contained in column name or vice versa
        for key in api_lookup:
            if key in col_lower or col_lower in key:
                return key
        return None
