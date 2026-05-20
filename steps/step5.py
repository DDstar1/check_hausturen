"""Step 5 — Results table with export to CSV."""

import os
import csv

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
)
from PySide6.QtGui import QColor

from utils import RESULT_HEADERS


class Step5(QWidget):
    def __init__(self):
        super().__init__()
        self.results = []
        self._headers = RESULT_HEADERS
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 28, 40, 28)

        title = QLabel("Step 5 — Results")
        title.setObjectName("step_title")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.count_lbl = QLabel("0 rows")
        self.count_lbl.setStyleSheet("color: #a6adc8;")
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self._export)
        top.addWidget(self.count_lbl)
        top.addStretch()
        top.addWidget(btn_export)
        layout.addLayout(top)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._headers))
        self.table.setHorizontalHeaderLabels(self._headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { alternate-background-color: #252538; }")
        layout.addWidget(self.table, stretch=1)

    def reset(self, headers: list):
        """Clear results and reconfigure columns for a new run."""
        self._headers = headers
        self.results.clear()
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.count_lbl.setText("0 rows")

    def add_row(self, row_data):
        self.results.append(row_data)
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, val in enumerate(row_data):
            item = QTableWidgetItem(str(val))
            v = str(val).lower()
            if v == "true":
                item.setForeground(QColor("#a6e3a1"))
            elif v == "false":
                item.setForeground(QColor("#f38ba8"))
            elif v == "n/a":
                item.setForeground(QColor("#6c7086"))
            self.table.setItem(r, c, item)
        self.count_lbl.setText(f"{len(self.results)} rows")

    def _export(self):
        os.makedirs("results", exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", os.path.join("results", "results.csv"), "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self._headers)
            w.writerows(self.results)
        QMessageBox.information(self, "Exported", f"Saved to:\n{path}")
