"""SetProductsWorker — updates WooCommerce products one-by-one with per-product confirmation."""

import threading
import html as _html

from PySide6.QtCore import QThread, Signal
import requests
from requests.auth import HTTPBasicAuth

from utils import excel_value_to_slug, parse_price

SET_HEADERS = ["Name", "Category", "Material", "Product ID", "Status", "URL"]


def _api_get(endpoint: str, store: dict, params: dict = None):
    auth = HTTPBasicAuth(store["consumer_key"], store["consumer_secret"])
    base = f"{store['url'].rstrip('/')}/wp-json/wc/v3"
    r = requests.get(f"{base}/{endpoint}", auth=auth, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _api_put(endpoint: str, store: dict, payload: dict):
    base   = f"{store['url'].rstrip('/')}/wp-json/wc/v3"
    params = {"consumer_key": store["consumer_key"], "consumer_secret": store["consumer_secret"]}
    r = requests.put(f"{base}/{endpoint}", params=params, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _api_post(endpoint: str, store: dict, payload: dict):
    base   = f"{store['url'].rstrip('/')}/wp-json/wc/v3"
    params = {"consumer_key": store["consumer_key"], "consumer_secret": store["consumer_secret"]}
    r = requests.post(f"{base}/{endpoint}", params=params, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


class SetProductsWorker(QThread):
    log         = Signal(str)
    progress    = Signal(int, int)
    row_ready   = Signal(list)
    finished    = Signal()
    product_set = Signal(str, str)  # (product_id, permalink)

    def __init__(self, excel_rows: list, store: dict, terms_cache: dict = None,
                 attrs_list: list = None, custom_checks: list = None):
        super().__init__()
        self.excel_rows      = excel_rows
        self.store           = store
        self._terms_cache    = terms_cache or {}
        self._attrs_list     = attrs_list or []
        self._custom_checks  = custom_checks or []  # [(attr_name, val_slug), ...]
        self._stop           = False
        self._confirm_event  = threading.Event()

    def stop(self):
        self._stop = True
        self._confirm_event.set()

    def confirm(self):
        self._confirm_event.set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        items = [(row, mat) for row in self.excel_rows for mat in row["materials"]]
        total = len(items)
        self.log.emit(f"Starting — {total} product(s) to set.\n")

        for idx, (row, mat) in enumerate(items):
            if self._stop:
                self.log.emit("[STOPPED]")
                break
            self._confirm_event.clear()
            self._set_product(row, mat, idx + 1, total)
            if self._stop:
                break
            if idx < total - 1:
                self._confirm_event.wait()

        self.log.emit("\nAll products processed.")
        self.finished.emit()

    # ------------------------------------------------------------------
    # Per-product update
    # ------------------------------------------------------------------

    def _set_product(self, row: dict, mat: dict, index: int, total: int):
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
            self.row_ready.emit([name, category, material, pid, "ERROR", str(e)])
            self.progress.emit(index, total)
            self.product_set.emit(pid, "")
            return

        permalink = product.get("permalink", "")
        payload   = {}

        base_price = mat.get("base_price", "").strip()
        ab_price   = mat.get("ab_price", "").strip()
        if base_price:
            payload["regular_price"] = base_price.replace(",", ".")
        if ab_price:
            payload["sale_price"] = ab_price.replace(",", ".")
            ab_num = parse_price(ab_price)
            if ab_num is not None:
                ab_str = str(int(ab_num)) if ab_num == int(ab_num) else f"{ab_num:.2f}"
                payload["meta_data"] = [
                    {
                        "key": "tm_meta_cpf",
                        "value": {
                            "mode": "settings",
                            "price_display_mode": "from",
                            "price_display_override": ab_str,
                            "price_display_override_to": "",
                            "price_display_override_sale": "",
                            "override_display": "",
                            "override_final_total_box": "",
                            "override_show_options_total": "",
                            "override_show_final_total": "",
                        },
                    }
                ]

        attrs_payload, default_attrs = self._build_attrs_payload(
            row.get("attr_values", {}), product, self._custom_checks
        )
        if attrs_payload:
            payload["attributes"] = attrs_payload
        if default_attrs:
            payload["default_attributes"] = default_attrs

        if not payload:
            self.log.emit("  Nothing to set — no price or attribute data in row.")
            self.row_ready.emit([name, category, material, pid, "SKIPPED", permalink])
            self.progress.emit(index, total)
            self.product_set.emit(pid, permalink)
            return

        self.log.emit(f"  Setting: {list(payload.keys())}")

        try:
            updated   = _api_put(f"products/{pid}", self.store, payload)
            permalink = updated.get("permalink", permalink)
            self.log.emit(f"  [OK] Product {pid} updated.")
        except Exception as e:
            self.log.emit(f"  [ERROR] PUT failed: {e}")
            self.row_ready.emit([name, category, material, pid, "ERROR", str(e)])
            self.progress.emit(index, total)
            self.product_set.emit(pid, permalink)
            return

        # Create or update the single variation with all default attributes + prices
        self._ensure_variation(pid, product, default_attrs, base_price, ab_price)

        self.log.emit(f"  URL: {permalink}")
        self.row_ready.emit([name, category, material, pid, "SET", permalink])
        self.progress.emit(index, total)
        self.product_set.emit(pid, permalink)

    # ------------------------------------------------------------------
    # Variation helpers
    # ------------------------------------------------------------------

    def _ensure_variation(self, pid: str, product: dict, default_attrs: list,
                          base_price: str, ab_price: str):
        var_payload = {
            "attributes": [
                {"id": a["id"], "name": a["name"], "option": a["option"]}
                for a in default_attrs
            ],
        }
        if base_price:
            var_payload["regular_price"] = base_price.replace(",", ".")
        if ab_price:
            var_payload["sale_price"] = ab_price.replace(",", ".")

        existing = product.get("variations", [])
        try:
            if existing:
                vid = existing[0]
                _api_put(f"products/{pid}/variations/{vid}", self.store, var_payload)
                self.log.emit(f"  [OK] Variation {vid} updated.")
            else:
                result = _api_post(f"products/{pid}/variations", self.store, var_payload)
                self.log.emit(f"  [OK] Variation {result['id']} created.")
        except Exception as e:
            self.log.emit(f"  [WARN] Variation update failed: {e}")

    # ------------------------------------------------------------------
    # Attribute helpers
    # ------------------------------------------------------------------

    def _build_attrs_payload(self, attr_values: dict, product: dict,
                             custom_checks: list = None) -> tuple:
        """Returns (attributes_list, default_attributes_list) for the PUT payload.

        Uses the globally-fetched attrs_list so attributes not yet on the product
        can still be looked up and added.
        """
        if not attr_values and not custom_checks:
            return [], []

        # Global attribute lookup (name_lower → {id, name})
        global_by_name = {a["name"].lower(): a for a in self._attrs_list}

        # Existing product attributes keyed by id (preserve position/options/etc.)
        existing_by_id = {a["id"]: a for a in product.get("attributes", [])}
        new_attrs      = dict(existing_by_id)

        default_attrs = []

        for col_name, excel_val in attr_values.items():
            col_lower = col_name.lower()

            # Find matching global WooCommerce attribute
            wc_attr = global_by_name.get(col_lower) or next(
                (a for k, a in global_by_name.items() if k in col_lower or col_lower in k),
                None,
            )
            if wc_attr is None:
                self.log.emit(f"  [WARN] Attribute not found in WooCommerce: '{col_name}'")
                continue

            attr_id   = wc_attr["id"]
            attr_name = wc_attr["name"]

            # Resolve term slug from display value
            term_map  = self._terms_cache.get(attr_id, {})  # slug → display_name
            inv       = {v.lower(): slug for slug, v in term_map.items()}
            term_slug = inv.get(excel_val.lower())
            if term_slug is None:
                term_slug = excel_value_to_slug(excel_val) or excel_val.lower()
                self.log.emit(
                    f"  [WARN] Term '{excel_val}' not in cache for '{attr_name}', "
                    f"using slug '{term_slug}'"
                )

            display_name = term_map.get(term_slug, excel_val)
            self.log.emit(f"  Setting '{attr_name}' = '{excel_val}' (slug: '{term_slug}')")

            # If attribute not already on product, add it with only this row's value as option
            if attr_id not in new_attrs:
                new_attrs[attr_id] = {
                    "id":        attr_id,
                    "name":      attr_name,
                    "position":  len(new_attrs),
                    "visible":   False,
                    "variation": True,
                    "options":   [display_name],
                }
                self.log.emit(f"  Adding attribute '{attr_name}' to product")

            default_attrs.append({"id": attr_id, "name": attr_name, "option": term_slug})

        # Merge custom checks — already have attr_name + val_slug directly
        for attr_name, val_slug in (custom_checks or []):
            wc_attr = global_by_name.get(attr_name.lower()) or next(
                (a for k, a in global_by_name.items()
                 if k in attr_name.lower() or attr_name.lower() in k),
                None,
            )
            if wc_attr is None:
                self.log.emit(f"  [WARN] Custom check attribute not found: '{attr_name}'")
                continue

            attr_id      = wc_attr["id"]
            attr_name_wc = wc_attr["name"]
            term_map     = self._terms_cache.get(attr_id, {})
            display_name = term_map.get(val_slug, val_slug)

            self.log.emit(f"  Setting (custom) '{attr_name_wc}' = '{display_name}' (slug: '{val_slug}')")

            if attr_id not in new_attrs:
                new_attrs[attr_id] = {
                    "id":        attr_id,
                    "name":      attr_name_wc,
                    "position":  len(new_attrs),
                    "visible":   False,
                    "variation": True,
                    "options":   [display_name],
                }
            else:
                existing_opts = new_attrs[attr_id].get("options", [])
                if display_name not in existing_opts:
                    new_attrs[attr_id]["options"] = existing_opts + [display_name]
            default_attrs.append({"id": attr_id, "name": attr_name_wc, "option": val_slug})

        return list(new_attrs.values()), default_attrs
