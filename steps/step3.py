"""Step 3 — Custom variable checks with dropdowns populated from cached WooCommerce data."""

import html as _html

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QComboBox, QListWidget, QSizePolicy,
)
from PySide6.QtCore import Qt


class Step3(QWidget):
    def __init__(self):
        super().__init__()
        self.custom_checks = []
        self._terms_cache  = {}   # attr_id -> {slug: display_name}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 28, 40, 28)

        title = QLabel("Step 3 — Custom Variables")
        title.setObjectName("step_title")
        layout.addWidget(title)

        sub = QLabel(
            "Add extra attribute checks applied to every product "
            "(e.g. Material = Aluminium). Values are loaded from the website."
        )
        sub.setObjectName("step_sub")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        add_group = QGroupBox("Add Custom Check")
        agl = QVBoxLayout(add_group)

        self.status_lbl = QLabel("Waiting for attribute data…")
        self.status_lbl.setStyleSheet("color: #6c7086; font-style: italic;")
        agl.addWidget(self.status_lbl)

        row = QHBoxLayout()

        self.attr_combo = QComboBox()
        self.attr_combo.setEnabled(False)
        self.attr_combo.setPlaceholderText("Attribute…")
        self.attr_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.attr_combo.currentIndexChanged.connect(self._on_attr_changed)

        self.val_combo = QComboBox()
        self.val_combo.setEnabled(False)
        self.val_combo.setPlaceholderText("Value…")
        self.val_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.btn_add = QPushButton("Add")
        self.btn_add.setEnabled(False)
        self.btn_add.clicked.connect(self._add)

        row.addWidget(self.attr_combo, 2)
        row.addWidget(self.val_combo, 2)
        row.addWidget(self.btn_add)
        agl.addLayout(row)
        layout.addWidget(add_group)

        list_group = QGroupBox("Current Custom Checks")
        lgl = QVBoxLayout(list_group)
        self.list_widget = QListWidget()
        btn_remove = QPushButton("Remove Selected")
        btn_remove.setProperty("danger", True)
        btn_remove.clicked.connect(self._remove)
        lgl.addWidget(self.list_widget)
        lgl.addWidget(btn_remove, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(list_group, stretch=1)

    # ------------------------------------------------------------------
    # Called by MainWindow once validation is done
    # ------------------------------------------------------------------

    def load_attributes(self, attrs_list: list, terms_cache: dict):
        """Populate dropdowns from pre-fetched data. No network calls here."""
        self._terms_cache = terms_cache

        self.attr_combo.blockSignals(True)
        self.attr_combo.clear()
        for a in attrs_list:
            self.attr_combo.addItem(a["name"], a["id"])
        self.attr_combo.blockSignals(False)

        if attrs_list:
            self.attr_combo.setEnabled(True)
            self.status_lbl.setText(f"{len(attrs_list)} attribute(s) loaded.")
            self._on_attr_changed(0)
        else:
            self.status_lbl.setText("No attributes received — check API connection.")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_attr_changed(self, index):
        if index < 0:
            return
        attr_id = self.attr_combo.itemData(index)
        terms   = self._terms_cache.get(attr_id, {})
        self.val_combo.clear()
        for slug, name in terms.items():
            self.val_combo.addItem(name, slug)
        enabled = len(terms) > 0
        self.val_combo.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)

    def _add(self):
        attr_name = self.attr_combo.currentText()
        val_name  = self.val_combo.currentText()
        val_slug  = self.val_combo.currentData() or val_name.lower()
        if not attr_name or not val_name:
            return
        self.list_widget.addItem(f"{attr_name}  ->  {val_name}")
        self.custom_checks.append((attr_name, val_slug))
        print(f"[DEBUG] added custom check: {self.custom_checks}")

    def _remove(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.list_widget.takeItem(row)
            self.custom_checks.pop(row)

    def get_custom_checks(self):
        return list(self.custom_checks)
