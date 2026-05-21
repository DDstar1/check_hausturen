"""MainWindow — wizard shell with navigation bar."""

import html as _html

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMessageBox,
    QDialog, QTextEdit, QDialogButtonBox, QComboBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QGraphicsBlurEffect

from steps import StepMode, StepCat, Step1, Step2, Step3, Step4, Step5
from worker import ApiWorker, _api_get
from worker_compare import CompareWorker, HEADERS_W2M, HEADERS_M2W
from worker_set import SetProductsWorker, SET_HEADERS
from overlay import LoadingOverlay
from utils import excel_value_to_slug, RESULT_HEADERS


# Attrs/terms fetched once per store URL for the lifetime of the process
_ATTRS_CACHE: dict[str, tuple[list, dict]] = {}  # url → (wc_attrs_raw, terms_cache)


class _ValidationThread(QThread):
    """Runs WooCommerce attribute/term validation in the background."""
    done   = Signal(list, list, list, object)
    failed = Signal(str)

    def __init__(self, store: dict, selected_var_cols: list, excel_data: dict):
        super().__init__()
        self.store             = store
        self.selected_var_cols = selected_var_cols
        self.excel_data        = excel_data

    def run(self):
        try:
            ok, issues, attrs_list, terms_cache = self._validate()
            self.done.emit(ok, issues, attrs_list, terms_cache)
        except Exception as e:
            self.failed.emit(str(e))

    def _validate(self):
        url = self.store["url"]
        if url in _ATTRS_CACHE:
            wc_attrs, terms_cache = _ATTRS_CACHE[url]
        else:
            wc_attrs = _api_get("products/attributes", self.store, {"per_page": 100})
            terms_cache = {}
            for a in wc_attrs:
                try:
                    raw = _api_get(
                        f"products/attributes/{a['id']}/terms",
                        self.store,
                        {"per_page": 100},
                    )
                    terms_cache[a["id"]] = {
                        t["slug"]: _html.unescape(t["name"]) for t in raw
                    }
                except Exception:
                    terms_cache[a["id"]] = {}
            _ATTRS_CACHE[url] = (wc_attrs, terms_cache)

        def _norm(s):
            s = s.replace("_", "-")
            return s[3:] if s.startswith("pa-") else s

        attr_by_slug = {}
        for a in wc_attrs:
            attr_by_slug[_norm(a["slug"])] = a
            ns = excel_value_to_slug(a["name"])
            if ns:
                attr_by_slug.setdefault(ns, a)

        ok_lines, issues = [], []

        for col_name, attr_slug in self.selected_var_cols:
            wc_attr = attr_by_slug.get(attr_slug) or next(
                (a for a in wc_attrs if a["name"].lower() in col_name.lower()), None
            )
            if wc_attr is None:
                issues.append(f"✗ '{col_name}' — not found as a WooCommerce attribute group")
                continue

            decoded_terms = list(terms_cache.get(wc_attr["id"], {}).values())
            valid_names   = {n.lower() for n in decoded_terms}
            excel_vals    = self.excel_data.get(col_name, set())
            bad = [v for v in excel_vals if v.lower() not in valid_names]

            if bad:
                valid_list = "".join(f"    ○ {n}\n" for n in sorted(decoded_terms, key=str.lower))
                issues.append(
                    f"✗ '{col_name}' → '{wc_attr['name']}' — "
                    f"{len(bad)} unrecognised value(s):\n"
                    + "".join(f"    • {v}\n" for v in bad)
                    + f"  Possible values in this group ({len(decoded_terms)}):\n"
                    + valid_list
                )
            else:
                ok_lines.append(
                    f"✓ '{col_name}' → '{wc_attr['name']}' "
                    f"({len(excel_vals)} unique value(s) all valid, "
                    f"{len(decoded_terms)} terms on site)"
                )

        attrs_list = [{"id": a["id"], "name": _html.unescape(a["name"])} for a in wc_attrs]
        return ok_lines, issues, attrs_list, terms_cache


# ── Stack indices ──────────────────────────────────────────────────────────────
_IDX_MODE = 0
_IDX_S1   = 1
_IDX_S2   = 2
_IDX_S3   = 3
_IDX_S4   = 4
_IDX_S5   = 5
_IDX_CAT  = 6


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("check_hastur — Product Validator")
        self.setMinimumSize(960, 680)
        self.worker         = None
        self.compare_worker = None
        self.set_worker     = None
        self._wb            = None
        self._sheet_name    = None
        self._table_ref     = None
        self._store         = None
        self._attrs_list    = []
        self._terms_cache   = {}
        self._chosen_prefix = None
        self._mode          = "check_masterlist"
        self._compare_config = None

        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # Steps
        self.stack  = QStackedWidget()
        self.smode  = StepMode()
        self.s1     = Step1()
        self.s2     = Step2()
        self.s3     = Step3()
        self.s4     = Step4()
        self.s5     = Step5()
        self.scat   = StepCat()
        for s in (self.smode, self.s1, self.s2, self.s3, self.s4, self.s5, self.scat):
            self.stack.addWidget(s)
        ml.addWidget(self.stack, stretch=1)

        # Nav bar
        nav = QFrame()
        nav.setObjectName("nav_bar")
        nav.setFixedHeight(58)
        navl = QHBoxLayout(nav)
        navl.setContentsMargins(24, 8, 24, 8)
        self.btn_back = QPushButton("← Back")
        self.btn_back.setEnabled(False)
        self.btn_next = QPushButton("Next →")
        self.step_lbl = QLabel("")
        self.step_lbl.setStyleSheet("color: #6c7086;")
        navl.addWidget(self.btn_back)
        navl.addStretch()
        navl.addWidget(self.step_lbl)
        navl.addStretch()
        navl.addWidget(self.btn_next)
        navl.addWidget(self.s4.btn_start)
        navl.addWidget(self.s4.btn_stop)
        navl.addWidget(self.s4.btn_confirm)
        self.s4.btn_start.hide()
        self.s4.btn_stop.hide()
        self.s4.btn_confirm.hide()
        ml.addWidget(nav)

        self.btn_back.clicked.connect(self._go_back)
        self.btn_next.clicked.connect(self._go_next)
        self.s4.btn_start.clicked.connect(self._start)
        self.s4.btn_stop.clicked.connect(self._stop)
        self.s4.btn_confirm.clicked.connect(self._confirm_product)
        self.smode.mode_chosen.connect(self._on_mode_chosen)

        self._overlay   = LoadingOverlay(central)
        self._nav_frame = nav
        self._val_thread = None
        self._blur_stack = None
        self._blur_nav   = None

        self._update_nav()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._overlay.isVisible():
            self._overlay.setGeometry(self.centralWidget().rect())

    # ------------------------------------------------------------------
    # Overlay helpers
    # ------------------------------------------------------------------

    def _show_overlay(self, text: str):
        self._blur_stack = QGraphicsBlurEffect()
        self._blur_stack.setBlurRadius(6)
        self._blur_nav = QGraphicsBlurEffect()
        self._blur_nav.setBlurRadius(6)
        self.stack.setGraphicsEffect(self._blur_stack)
        self._nav_frame.setGraphicsEffect(self._blur_nav)
        self._overlay.setGeometry(self.centralWidget().rect())
        self._overlay.start(text)

    def _stop_spinner(self):
        self._overlay.stop()

    def _remove_blur(self):
        self.stack.setGraphicsEffect(None)
        self._nav_frame.setGraphicsEffect(None)
        self._blur_stack = None
        self._blur_nav   = None

    # ------------------------------------------------------------------
    # Mode selection
    # ------------------------------------------------------------------

    def _on_mode_chosen(self, mode: str):
        self._mode = mode
        if mode in ("check_masterlist", "set_products"):
            self.stack.setCurrentIndex(_IDX_S1)
        else:
            self.stack.setCurrentIndex(_IDX_CAT)
        self._update_nav()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _idx(self):
        return self.stack.currentIndex()

    def _go_back(self):
        i = self._idx()
        if i == _IDX_CAT:
            self.stack.setCurrentIndex(_IDX_MODE)
        elif i == _IDX_S4 and self._mode == "compare_category":
            self.stack.setCurrentIndex(_IDX_CAT)
        elif i > _IDX_MODE:
            self.stack.setCurrentIndex(i - 1)
        self._update_nav()

    def _go_next(self):
        i = self._idx()

        if i == _IDX_S1:
            result = self.s1.get_table()
            if not result:
                QMessageBox.warning(self, "No table", "Please select an Excel file and table first.")
                return
            self._store = self.s1.get_store()
            if not self._store:
                QMessageBox.warning(self, "Missing credentials", "Please enter the Consumer Key and Consumer Secret for the selected store.")
                return
            self._wb, self._sheet_name, self._table_ref = result
            self.s2.load_columns(self._wb, self._sheet_name, self._table_ref)

        elif i == _IDX_S2:
            _, id_columns, selected_var_cols = self.s2.get_config()
            if not id_columns:
                QMessageBox.warning(
                    self, "No ID columns",
                    "Could not auto-detect any product ID columns.\n"
                    "Name your ID columns so they end with '_id'."
                )
                return
            duplicates = self._find_duplicate_ids(id_columns)
            if duplicates:
                QMessageBox.warning(
                    self, "Duplicate IDs",
                    "The following product IDs appear more than once:\n\n"
                    + ", ".join(sorted(duplicates))
                    + "\n\nPlease fix the Excel file before continuing."
                )
                return
            self._start_column_validation(selected_var_cols)
            return

        elif i == _IDX_CAT:
            config = self.scat.get_config()
            if not config:
                return
            self._compare_config = config
            self.s4.log.clear()
            self.s4.progress.setValue(0)
            self.s4.status_lbl.setText("Ready. Click ▶ Start to begin.")
            headers = HEADERS_W2M if config["mode"] == "website_to_masterlist" else HEADERS_M2W
            self.s5.reset(headers)
            self.stack.setCurrentIndex(_IDX_S4)
            self._update_nav()
            return

        if _IDX_S1 <= i < _IDX_S5:
            self.stack.setCurrentIndex(i + 1)
            self._update_nav()

    def _update_nav(self):
        i = self._idx()
        if i == _IDX_MODE:
            self.step_lbl.setText("")
            self.btn_back.setEnabled(False)
            self.btn_next.setVisible(False)
            self.s4.btn_start.setVisible(False)
            self.s4.btn_stop.setVisible(False)
            self.s4.btn_confirm.setVisible(False)
        elif i == _IDX_CAT:
            self.step_lbl.setText("Category Compare")
            self.btn_back.setEnabled(True)
            self.btn_next.setVisible(True)
            self.btn_next.setText("Next →")
            self.s4.btn_start.setVisible(False)
            self.s4.btn_stop.setVisible(False)
            self.s4.btn_confirm.setVisible(False)
        else:
            step_num = i  # indices 1-5 map to steps 1-5
            self.step_lbl.setText(f"Step {step_num} of 5")
            self.btn_back.setEnabled(i > _IDX_MODE)
            self.btn_next.setVisible(_IDX_S1 <= i < _IDX_S4)
            self.btn_next.setText("Next →")
            on_s4 = (i == _IDX_S4)
            self.s4.btn_start.setVisible(on_s4)
            self.s4.btn_stop.setVisible(on_s4)
            if on_s4 and self._mode == "set_products":
                self.s4.btn_start.setText("▶  Start Setting")
            elif on_s4:
                self.s4.btn_start.setText("▶  Start Validation")
            if not on_s4:
                self.s4.btn_confirm.setVisible(False)

    # ------------------------------------------------------------------
    # Attribute column pre-validation (step 2 → 3)
    # ------------------------------------------------------------------

    def _find_duplicate_ids(self, id_columns: list) -> set:
        ws = self._wb[self._sheet_name]
        table_cells = ws[self._table_ref]
        headers = [str(c.value).strip() if c.value else "" for c in table_cells[0]]

        seen, duplicates = {}, set()
        for row in table_cells[1:]:
            vals = [cell.value for cell in row]
            for id_info in id_columns:
                col = id_info["id_col"]
                if col not in headers:
                    continue
                raw = vals[headers.index(col)]
                if not raw or str(raw).strip().lower() in ("", "none"):
                    continue
                pid = str(raw).strip().split(".")[0]
                if pid in seen:
                    duplicates.add(pid)
                else:
                    seen[pid] = True
        return duplicates

    def _start_column_validation(self, selected_var_cols: list):
        if not selected_var_cols:
            self.s3.load_attributes(self._attrs_list, self._terms_cache)
            self.stack.setCurrentIndex(_IDX_S3)
            self._update_nav()
            return

        _, id_columns, _ = self.s2.get_config()
        chosen_prefix = None
        if len(id_columns) > 1:
            dlg = QDialog(self)
            dlg.setWindowTitle("Select Product Set")
            lay = QVBoxLayout(dlg)
            lay.addWidget(QLabel(
                "Multiple product ID columns were detected.\n"
                "Which set would you like to validate attribute values against?\n\n"
                "(Both sets share the same variables — pick one to run the check.)"
            ))
            combo = QComboBox()
            for idc in id_columns:
                combo.addItem(idc["prefix"].capitalize(), idc["prefix"])
            lay.addWidget(combo)
            bb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            bb.accepted.connect(dlg.accept)
            bb.rejected.connect(dlg.reject)
            lay.addWidget(bb)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            chosen_prefix = combo.currentData()

        self._chosen_prefix = chosen_prefix

        _, id_columns_all, _ = self.s2.get_config()
        cols_to_check = (
            [c for c in id_columns_all if c["prefix"] == chosen_prefix]
            if chosen_prefix else id_columns_all
        )
        missing_price_cols = []
        for idc in cols_to_check:
            prefix = idc["prefix"].capitalize()
            if not idc["base_price_col"]:
                missing_price_cols.append(f"  • {prefix}: missing base price column")
            if not idc["ab_price_col"]:
                missing_price_cols.append(f"  • {prefix}: missing Ab price column")
        if missing_price_cols:
            QMessageBox.warning(
                self, "Missing Price Columns",
                "The following price columns were not found:\n\n"
                + "\n".join(missing_price_cols)
                + "\n\nAdd these columns to your Excel file before continuing."
            )
            return

        ws          = self._wb[self._sheet_name]
        table_cells = ws[self._table_ref]
        headers     = [str(c.value).strip() if c.value else "" for c in table_cells[0]]

        excel_data = {}
        for col_name, _ in selected_var_cols:
            col_idx = headers.index(col_name) if col_name in headers else None
            if col_idx is None:
                continue
            vals = set()
            for row in table_cells[1:]:
                raw = row[col_idx].value
                if not raw or str(raw).strip() in ("", "None", "Nil", "-"):
                    continue
                vals.add(str(raw).strip())
            excel_data[col_name] = vals

        label = chosen_prefix.capitalize() if chosen_prefix else "products"
        self._show_overlay(f"Validating {label} attribute columns against WooCommerce…")

        self._val_thread = _ValidationThread(self._store, selected_var_cols, excel_data)
        self._val_thread.done.connect(self._on_validation_done)
        self._val_thread.failed.connect(self._on_validation_failed)
        self._val_thread.start()

    def _on_validation_done(self, ok_lines: list, issues: list, attrs_list: list, terms_cache: dict):
        self._attrs_list  = attrs_list
        self._terms_cache = terms_cache
        self._stop_spinner()

        if not issues:
            self._remove_blur()
            self.s3.load_attributes(attrs_list, terms_cache)
            self.stack.setCurrentIndex(_IDX_S3)
            self._update_nav()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Column Validation Issues")
        dlg.setMinimumSize(640, 400)
        lay = QVBoxLayout(dlg)

        summary = QLabel(
            f"<b>{len(ok_lines)} column(s) OK</b> — "
            f"<span style='color:#f38ba8'><b>{len(issues)} issue(s) found</b></span><br>"
            "You can go back to fix them or proceed anyway."
        )
        summary.setWordWrap(True)
        lay.addWidget(summary)

        report = QTextEdit()
        report.setReadOnly(True)
        report.setFontFamily("Consolas")
        report.setFontPointSize(10)
        report.setPlainText(
            "── OK ────────────────────────────────\n"
            + "\n".join(ok_lines)
            + "\n\n── Issues ────────────────────────────\n"
            + "\n".join(issues)
        )
        lay.addWidget(report, stretch=1)

        buttons = QDialogButtonBox()
        btn_proceed = buttons.addButton("Proceed Anyway", QDialogButtonBox.ButtonRole.AcceptRole)
        btn_back    = buttons.addButton("Go Back",        QDialogButtonBox.ButtonRole.RejectRole)
        btn_proceed.clicked.connect(dlg.accept)
        btn_back.clicked.connect(dlg.reject)
        lay.addWidget(buttons)

        proceed = dlg.exec() == QDialog.DialogCode.Accepted
        self._remove_blur()
        if proceed:
            self.s3.load_attributes(attrs_list, terms_cache)
            self.stack.setCurrentIndex(_IDX_S3)
            self._update_nav()

    def _on_validation_failed(self, error: str):
        self._stop_spinner()
        QMessageBox.warning(
            self, "Validation Error",
            f"Could not connect to the WooCommerce API:\n{error}\n\n"
            "Proceeding without column validation."
        )
        self._remove_blur()
        self.stack.setCurrentIndex(_IDX_S3)
        self._update_nav()

    # ------------------------------------------------------------------
    # Excel processing
    # ------------------------------------------------------------------

    def _build_rows(self):
        ws = self._wb[self._sheet_name]
        special_cols, id_columns, selected_var_cols = self.s2.get_config()
        if self._chosen_prefix:
            id_columns = [c for c in id_columns if c["prefix"] == self._chosen_prefix]

        table_cells = ws[self._table_ref]
        headers = [str(cell.value).strip() if cell.value else "" for cell in table_cells[0]]

        def ci(name):
            return headers.index(name) if name and name in headers else None

        name_i = ci(special_cols.get("name"))
        cat_i  = ci(special_cols.get("category"))

        rows = []
        for table_row in table_cells[1:]:
            vals = [cell.value for cell in table_row]
            name     = str(vals[name_i]).strip() if name_i is not None and vals[name_i] else ""
            category = str(vals[cat_i]).strip()  if cat_i  is not None and vals[cat_i]  else ""

            materials = []
            for id_info in id_columns:
                id_i = ci(id_info["id_col"])
                bp_i = ci(id_info["base_price_col"]) if id_info["base_price_col"] else None
                ap_i = ci(id_info["ab_price_col"])   if id_info["ab_price_col"]   else None

                raw_id = str(vals[id_i]).strip() if id_i is not None and vals[id_i] else ""
                if not raw_id or raw_id.lower() in ("none", ""):
                    continue

                product_id = raw_id.split(".")[0]
                base_price = str(vals[bp_i]).strip() if bp_i is not None and vals[bp_i] else ""
                ab_price   = str(vals[ap_i]).strip() if ap_i is not None and vals[ap_i] else ""

                materials.append({
                    "prefix":     id_info["prefix"],
                    "product_id": product_id,
                    "base_price": base_price,
                    "ab_price":   ab_price,
                })

            if not materials:
                continue

            attr_values  = {}
            absent_attrs = set()
            for col_name, _ in selected_var_cols:
                if col_name in headers:
                    val     = vals[headers.index(col_name)]
                    display = str(val).strip() if val else ""
                    if display and display not in ("None", "Nil", "-"):
                        attr_values[col_name] = display
                    else:
                        absent_attrs.add(col_name)

            rows.append({
                "name":        name,
                "category":    category,
                "materials":   materials,
                "attr_values": attr_values,
                "absent_attrs": absent_attrs,
            })
        return rows

    # ------------------------------------------------------------------
    # Worker lifecycle — Check Masterlist
    # ------------------------------------------------------------------

    def _start(self):
        if self._mode == "set_products":
            self._start_set()
            return
        if self._mode != "check_masterlist":
            self._start_compare()
            return

        try:
            rows = self._build_rows()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not process Excel:\n{e}")
            return
        if not rows:
            QMessageBox.warning(self, "No rows", "No product rows with an ID found.")
            return

        custom = self.s3.get_custom_checks()

        total_products = sum(len(r["materials"]) for r in rows)
        self.s4.log.clear()
        self.s4.progress.setValue(0)
        self.s4.progress.setMaximum(total_products)
        self.s4.status_lbl.setText(f"Starting… ({total_products} products across {len(rows)} rows)")
        self.s5.reset(list(RESULT_HEADERS))
        self.s5.count_lbl.setText("0 rows")

        self.worker = ApiWorker(rows, custom, self._store, self._terms_cache)
        self.worker.log.connect(self.s4.append_log)
        self.worker.progress.connect(self.s4.set_progress)
        self.worker.row_ready.connect(self.s5.add_row)
        self.worker.finished.connect(self._on_done)

        self.s4.btn_start.setEnabled(False)
        self.s4.btn_stop.setEnabled(True)
        self.btn_back.setEnabled(False)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
        if self.compare_worker:
            self.compare_worker.stop()
        if self.set_worker:
            self.set_worker.stop()
        self.s4.btn_confirm.setVisible(False)
        self.s4.status_lbl.setText("Stopping…")

    def _on_done(self):
        self.s4.btn_start.setEnabled(True)
        self.s4.btn_stop.setEnabled(False)
        self.s4.btn_confirm.setVisible(False)
        self.btn_back.setEnabled(True)
        count = len(self.s5.results)
        if self._mode == "set_products":
            self.s4.status_lbl.setText(f"Done — {count} product(s) set.")
        else:
            self.s4.status_lbl.setText(f"Done — {count} products checked.")
        self.stack.setCurrentIndex(_IDX_S5)
        self._update_nav()

    # ------------------------------------------------------------------
    # Worker lifecycle — Set Products mode
    # ------------------------------------------------------------------

    def _start_set(self):
        try:
            rows = self._build_rows()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not process Excel:\n{e}")
            return
        if not rows:
            QMessageBox.warning(self, "No rows", "No product rows with an ID found.")
            return

        total_products = sum(len(r["materials"]) for r in rows)
        self.s4.log.clear()
        self.s4.progress.setValue(0)
        self.s4.progress.setMaximum(total_products)
        self.s4.status_lbl.setText(f"Starting… ({total_products} products across {len(rows)} rows)")
        self.s5.reset(list(SET_HEADERS))
        self.s5.count_lbl.setText("0 rows")

        custom = self.s3.get_custom_checks()
        self.set_worker = SetProductsWorker(rows, self._store, self._terms_cache, self._attrs_list, custom)
        self.set_worker.log.connect(self.s4.append_log)
        self.set_worker.progress.connect(self.s4.set_progress)
        self.set_worker.row_ready.connect(self.s5.add_row)
        self.set_worker.finished.connect(self._on_done)
        self.set_worker.product_set.connect(self._on_product_set)

        self.s4.btn_start.setEnabled(False)
        self.s4.btn_stop.setEnabled(True)
        self.btn_back.setEnabled(False)
        self.set_worker.start()

    def _on_product_set(self, pid: str, permalink: str):
        if permalink:
            self.s4.append_log(f"\n  URL: {permalink}")
        self.s4.btn_confirm.setVisible(True)
        self.s4.btn_confirm.setEnabled(True)

    def _confirm_product(self):
        self.s4.btn_confirm.setEnabled(False)
        self.s4.btn_confirm.setVisible(False)
        if self.set_worker:
            self.set_worker.confirm()

    # ------------------------------------------------------------------
    # Worker lifecycle — Compare modes
    # ------------------------------------------------------------------

    def _start_compare(self):
        if not self._compare_config:
            return

        self.s4.log.clear()
        self.s4.progress.setValue(0)
        self.s4.status_lbl.setText("Starting…")

        self.compare_worker = CompareWorker(self._compare_config)
        self.compare_worker.log.connect(self.s4.append_log)
        self.compare_worker.progress.connect(self.s4.set_progress)
        self.compare_worker.row_ready.connect(self.s5.add_row)
        self.compare_worker.finished.connect(self._on_compare_done)

        self.s4.btn_start.setEnabled(False)
        self.s4.btn_stop.setEnabled(True)
        self.btn_back.setEnabled(False)
        self.compare_worker.start()

    def _on_compare_done(self):
        self.s4.btn_start.setEnabled(True)
        self.s4.btn_stop.setEnabled(False)
        self.btn_back.setEnabled(True)
        self.s4.status_lbl.setText(f"Done — {len(self.s5.results)} issue(s) found.")
        self.stack.setCurrentIndex(_IDX_S5)
        self._update_nav()
