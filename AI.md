# check_hastur — Project State

## What this tool does
PySide6 wizard that reads product data from an Excel masterlist, visits each product page on `haustuerenshop.paultec.de` via Selenium, and validates a set of checks per product. Results are shown in a live table and exported to CSV.

---

## File Structure

| File | Role |
|---|---|
| `app.py` | Entry point — creates QApplication, loads stylesheet, shows MainWindow |
| `main_window.py` | Wizard shell (QStackedWidget), navigation, `_build_rows()`, worker lifecycle |
| `worker.py` | `ScraperWorker(QThread)` — all Selenium logic |
| `utils.py` | Shared constants and helper functions |
| `style.py` | QSS dark theme (Catppuccin Mocha) |
| `steps/step1.py` | Excel file picker + named-table selector |
| `steps/step2.py` | Column mapping (auto-detect special cols + variable checkboxes) |
| `steps/step3.py` | Custom variable checks (applied to every product) |
| `steps/step4.py` | Run screen — Start/Stop, headless toggle, progress bar, live log |
| `steps/step5.py` | Results table + CSV export |
| `main.py` | Original CLI scraper (kept as fallback, not connected to GUI) |

---

## Wizard Flow

### Step 1 — Excel Setup
- Browse for `.xlsx` file
- Dropdown lists **Excel named table names** (not sheet names) — uses `ws.tables.values()` across all sheets
- The current masterlist has a table named `Table1` on `Sheet1` (range A1:Q7)

### Step 2 — Column Mapping
Auto-detected special columns (read-only labels):
- `name` — header is PRODUCTS / PRODUCT / NAME / PRODUKT
- `category` — header is KATEGORY / CATEGORY / KATEGORIE
- `link` — header contains "link" or "url"
- `ab_price` — header contains "ab" + "price/preis"
- `base_price` — header contains "base" + "price/preis"
- `price` — fallback: any header with "price" or "preis"

Variable columns (checkboxes, pre-checked if in `ATTR_COLUMN_MAP`):
- All `Rodenberg X` column name variants are in `ATTR_COLUMN_MAP` and will be pre-checked automatically

### Step 3 — Custom Variables
- Add `(attr_slug, expected_value)` pairs applied to every product
- **Both fields are slugified on Add** — paste raw text like `Rodenberg Füllung` or `Einsatzfüllung & Aufsatzfüllung`, it will be converted correctly
- Material is NOT auto-derived from the URL — add it here manually if needed

### Step 4 — Run
- Start/Stop buttons, headless toggle, progress bar, live log

### Step 5 — Results
- Table + CSV export

---

## Excel Masterlist Columns (Table1 / Sheet1)

| Column | Role |
|---|---|
| PRODUCTS | Product name |
| KATEGORY | Category |
| Rodenberg Füllung | → `rodenberg-fuellung` |
| Rodenberg Ausfuhrung | → `rodenberg-ausfuhrung` |
| Rodenberg Breite | → `rodenberg-breite` |
| Rodenberg Höhe | → `rodenberg-hoehe` |
| Rodenberg Element | → `rodenberg-element` |
| Rodenberg Verglasung | → `rodenberg-verglasung` |
| Rodenberg Lisenen | → `rodenberg-lisenen` |
| Rodenberg Farbe | → `rodenberg-farbe` |
| Rodenberg Seitenteil Breite | → `rodenberg-seitenteil-breite` |
| Product_Link | Product URL (auto-detected as `link`) |
| Product_Base_price | Base price (auto-detected as `base_price`) |
| Ab_price | AB price (auto-detected as `ab_price`) |

---

## Result Columns (CSV / Table)

```
Product Name | Category |
Button Disabled |
AB Price Showing | AB Price (Website) | Excel AB Price | AB Price Match |
Website Base Price | Excel Base Price | Base Price Match |
Has Form | Form Added |
Variables Match | Mismatch Description | URL
```

---

## Checks Performed Per Product

### 1. Button Disabled
CSS: `button.single_add_to_cart_button` — checks `disabled` class or `aria-disabled="true"`.

### 2. AB Price
CSS: `div.product-info.summary.col-fit...tc-init > div.price-wrapper > p`
- `AB Price Showing` = True if `span.from` is present in the price paragraph
- `AB Price (Website)` = the price amount text
- Compared against Excel `Ab_price` column → `AB Price Match`

### 3. Base Price
Computed as: `#tm-epo-totals dd.tm-final-totals span > span` **minus** `#tm-epo-totals dd.tm-options-totals span > span`
- Compared against Excel `Base_price` (or `Product_Base_price`) column → `Base Price Match`

### 4. Form Check
CSS: `li.tm-extra-product-options-field`
- `Has Form` = any such li exists
- `Form Added` = True if **none** of the li elements have height < 10px (empty li = form not configured)

### 5. Variable Match
Reads `data-product_variations` JSON from `form.variations_form`.
- **Non-empty Excel column** → value must match the corresponding `attribute_pa_*` key on the website
- **Empty Excel column** → that attribute must be **absent** from the website variations
- **Count check** → number of non-empty Excel attrs must equal number of matching website attrs
- Mismatches described in `Mismatch Description` column

---

## Slug Conversion (`excel_value_to_slug`)
- `Group 710` → `premium-group-710`
- `Premium 9` → `premium-9`
- Umlauts: ü→ue, ö→oe, ä→ae, ß→ss
- ` & ` → `-`
- Special post-processing aliases:
  - `turblatt` → `tuerfuellung`
  - `aufsatzfuellung-seitenteil` → `aufsatzfuellung`

---

## Price Parsing
German decimal format: `1.234,56` → `1234.56`. Match tolerance: ±€0.05.
`parse_price()` in `utils.py` is the shared helper used by both `prices_match()` and `_check_base_price()`.

---

## Dependencies
```
pip install PySide6 openpyxl selenium
```

## Run
```
python app.py
```
