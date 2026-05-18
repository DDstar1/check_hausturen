"""Step 1 — Store selection + Excel file + table selection."""

import os
import openpyxl

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QGroupBox, QMessageBox, QSizePolicy,
)

from utils import WOO_STORES


class Step1(QWidget):
    def __init__(self):
        super().__init__()
        self.wb = None
        self.file_path = ""
        self._table_map = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(40, 28, 40, 28)

        title = QLabel("Step 1 — Select Store & Excel File")
        title.setObjectName("step_title")
        layout.addWidget(title)

        sub = QLabel(
            "Pick which WooCommerce store to validate against, "
            "then choose your masterlist Excel file and table."
        )
        sub.setObjectName("step_sub")
        sub.setWordWrap(True)
        layout.addWidget(sub)
        layout.addSpacing(8)

        # ── Store selector ───────────────────────────────────────────────────
        sg = QGroupBox("WooCommerce Store")
        sgl = QHBoxLayout(sg)
        self.store_combo = QComboBox()
        self.store_combo.addItems(list(WOO_STORES.keys()))
        self.store_url_lbl = QLabel()
        self.store_url_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.store_combo.currentTextChanged.connect(self._on_store_changed)
        self._on_store_changed(self.store_combo.currentText())
        sgl.addWidget(self.store_combo)
        sgl.addWidget(self.store_url_lbl, stretch=1)
        layout.addWidget(sg)

        # ── Excel file ───────────────────────────────────────────────────────
        fg = QGroupBox("Excel File")
        fgl = QHBoxLayout(fg)
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #6c7086;")
        self.file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        btn = QPushButton("Browse…")
        btn.clicked.connect(self._browse)
        fgl.addWidget(self.file_label)
        fgl.addWidget(btn)
        layout.addWidget(fg)

        # ── Table ────────────────────────────────────────────────────────────
        tg = QGroupBox("Table")
        tgl = QVBoxLayout(tg)
        self.table_combo = QComboBox()
        self.table_combo.setEnabled(False)
        self.table_info_lbl = QLabel("")
        self.table_info_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        tgl.addWidget(self.table_combo)
        tgl.addWidget(self.table_info_lbl)
        layout.addWidget(tg)

        layout.addStretch()

    def _on_store_changed(self, name):
        store = WOO_STORES.get(name, {})
        self.store_url_lbl.setText(store.get("url", ""))

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Excel file", "", "Excel Files (*.xlsx *.xlsm)")
        if not path:
            return
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
            return

        table_map = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for tbl in ws.tables.values():
                table_map[tbl.name] = (sheet_name, tbl)

        if not table_map:
            QMessageBox.warning(
                self, "No tables found",
                "No Excel tables (Insert → Table) were found in this workbook.\n"
                "Please format your data as a table in Excel first."
            )
            return

        self.wb = wb
        self._table_map = table_map
        self.file_path = path
        self.file_label.setText(os.path.basename(path))
        self.file_label.setStyleSheet("color: #cdd6f4;")
        self.table_combo.clear()
        self.table_combo.addItems(sorted(table_map.keys()))
        self.table_combo.setEnabled(True)

    def _on_table_changed(self, name):
        if name and name in self._table_map:
            sheet_name, tbl = self._table_map[name]
            self.table_info_lbl.setText(f"Sheet: {sheet_name}   Range: {tbl.ref}")
        else:
            self.table_info_lbl.setText("")

    def get_store(self) -> dict | None:
        """Returns the selected store config dict from WOO_STORES."""
        return WOO_STORES.get(self.store_combo.currentText())

    def get_table(self):
        """Returns (workbook, sheet_name, table_ref) or None."""
        name = self.table_combo.currentText()
        if not self.wb or not name or name not in self._table_map:
            return None
        sheet_name, tbl = self._table_map[name]
        return self.wb, sheet_name, tbl.ref
