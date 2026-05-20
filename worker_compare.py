"""CompareWorker — category vs masterlist comparison in a background thread."""

import requests
from requests.auth import HTTPBasicAuth

from PySide6.QtCore import QThread, Signal


HEADERS_W2M = ["Product Name", "Product ID", "Slug", "Status", "URL"]
HEADERS_M2W = ["Product Name", "Excel ID", "Status", "URL"]


def _api_get(endpoint, store, params=None):
    auth = HTTPBasicAuth(store["consumer_key"], store["consumer_secret"])
    base = f"{store['url'].rstrip('/')}/wp-json/wc/v3"
    r = requests.get(f"{base}/{endpoint}", auth=auth, params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _fetch_all(endpoint, store, extra=None):
    items, page = [], 1
    while True:
        batch = _api_get(endpoint, store, {"per_page": 100, "page": page, **(extra or {})})
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return items


def _get_category_id(cat_slug, store):
    cats = _api_get("products/categories", store, {"slug": cat_slug})
    if not cats:
        raise ValueError(f"Category not found: {cat_slug!r}")
    return cats[0]["id"]


class CompareWorker(QThread):
    log       = Signal(str)
    progress  = Signal(int, int)
    row_ready = Signal(list)
    finished  = Signal()

    def __init__(self, config: dict):
        super().__init__()
        self._store      = config["store"]
        self._wb         = config["wb"]
        self._sheet_name = config["sheet_name"]
        self._table_ref  = config["table_ref"]
        self._cat_slug   = config["cat_slug"]
        self._col_set    = config.get("col_set")
        self._mode       = config["mode"]
        self._stop       = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if self._mode == "website_to_masterlist":
                self._run_w2m()
            else:
                self._run_m2w()
        except Exception as e:
            self.log.emit(f"\n[ERROR] {e}")
        finally:
            self.finished.emit()

    # ── Website → Masterlist ──────────────────────────────────────────────────

    def _run_w2m(self):
        self.log.emit(f"Resolving category '{self._cat_slug}'…")
        cat_id = _get_category_id(self._cat_slug, self._store)
        self.log.emit(f"Category ID: {cat_id}")

        self.log.emit("Fetching products from website…")
        products = _fetch_all("products", self._store,
                              {"category": cat_id, "status": "publish"})
        self.log.emit(f"Found {len(products)} products on website.")

        excel_ids = self._build_excel_ids()
        self.log.emit(f"Loaded {len(excel_ids)} product IDs from Excel column '{self._col_set['id_col']}'.\n")

        total = len(products)
        not_found = 0
        for i, p in enumerate(products, 1):
            if self._stop:
                self.log.emit("[STOPPED]")
                break
            if str(p["id"]) not in excel_ids:
                self.row_ready.emit([
                    p["name"], str(p["id"]), p.get("slug", ""),
                    "not in Excel", p.get("permalink", ""),
                ])
                not_found += 1
            self.progress.emit(i, total)

        self.log.emit(f"\n{not_found} website product(s) not found in Excel.")

    def _build_excel_ids(self) -> set:
        ws = self._wb[self._sheet_name]
        cells = ws[self._table_ref]
        headers = [str(c.value).strip() if c.value else "" for c in cells[0]]
        id_col = self._col_set["id_col"] if self._col_set else None
        id_i   = headers.index(id_col) if id_col and id_col in headers else None
        if id_i is None:
            return set()
        ids = set()
        for row in cells[1:]:
            val = row[id_i].value
            if val and str(val).strip().lower() not in ("", "none"):
                ids.add(str(val).strip().split(".")[0])
        return ids

    # ── Masterlist → Website ──────────────────────────────────────────────────

    def _run_m2w(self):
        self.log.emit(f"Resolving category '{self._cat_slug}'…")
        cat_id = _get_category_id(self._cat_slug, self._store)
        self.log.emit(f"Category ID: {cat_id}")

        self.log.emit("Fetching all products in category from website…")
        products = _fetch_all("products", self._store, {"category": cat_id})
        website_ids = {str(p["id"]) for p in products}
        self.log.emit(f"Found {len(website_ids)} products in category on website.")

        rows = self._read_excel_rows()
        self.log.emit(f"Loaded {len(rows)} product rows from Excel.\n")

        total = len(rows)
        issues = 0
        for i, (name, pid) in enumerate(rows, 1):
            if self._stop:
                self.log.emit("[STOPPED]")
                break

            if not pid:
                self.row_ready.emit([name, "", "missing_id", ""])
                issues += 1
            elif pid not in website_ids:
                self.row_ready.emit([name, pid, "not_in_category", ""])
                issues += 1

            self.progress.emit(i, total)

        self.log.emit(f"\n{issues} issue(s) found across {total} row(s).")

    def _read_excel_rows(self) -> list:
        ws = self._wb[self._sheet_name]
        cells = ws[self._table_ref]
        headers = [str(c.value).strip() if c.value else "" for c in cells[0]]

        name_i = next(
            (i for i, h in enumerate(headers)
             if h.upper() in ("PRODUCTS", "PRODUCT", "NAME", "PRODUKT")),
            None,
        )
        id_col = self._col_set["id_col"] if self._col_set else None
        id_i   = headers.index(id_col) if id_col and id_col in headers else None

        rows = []
        for row in cells[1:]:
            vals = [cell.value for cell in row]
            name = str(vals[name_i]).strip() if name_i is not None and vals[name_i] else ""
            if not name or name in ("None", "-"):
                continue

            pid = ""
            if id_i is not None and vals[id_i]:
                raw = str(vals[id_i]).strip()
                if raw and raw.lower() not in ("none", ""):
                    pid = raw.split(".")[0]

            rows.append((name, pid))
        return rows
