"""Step 2 — Column mapping (ID columns + variable attribute checkboxes)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox,
    QScrollArea, QGroupBox, QFrame,
)

from utils import ATTR_COLUMN_MAP, SPECIAL_ROLES, find_id_columns, excel_value_to_slug


class Step2(QWidget):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.special_cols = {}
        self._id_columns = []
        self.col_checkboxes = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(40, 28, 40, 28)

        title = QLabel("Step 2 — Column Mapping")
        title.setObjectName("step_title")
        outer.addWidget(title)

        sub = QLabel(
            "ID columns and special columns are auto-detected. "
            "Tick attribute columns you want validated against the website."
        )
        sub.setObjectName("step_sub")
        sub.setWordWrap(True)
        outer.addWidget(sub)

        self.special_group = QGroupBox("Auto-detected Columns")
        self.special_inner = QVBoxLayout(self.special_group)
        outer.addWidget(self.special_group)

        var_group = QGroupBox("Variable Columns to Check")
        vgl = QVBoxLayout(var_group)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.var_container = QWidget()
        self.var_layout = QVBoxLayout(self.var_container)
        self.var_layout.setSpacing(4)
        scroll.setWidget(self.var_container)
        vgl.addWidget(scroll)
        outer.addWidget(var_group, stretch=1)

    def load_columns(self, wb, sheet_name, table_ref):
        ws = wb[sheet_name]
        table_cells = ws[table_ref]
        self.headers = [str(c.value).strip() if c.value else "" for c in table_cells[0]]

        for layout in (self.special_inner, self.var_layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        self.col_checkboxes.clear()
        self.special_cols.clear()
        self._id_columns = []

        assigned = set()

        # Auto-detect name / category
        for role, detect in SPECIAL_ROLES.items():
            for h in self.headers:
                if h and h not in assigned and detect(h):
                    self.special_cols[role] = h
                    assigned.add(h)
                    lbl = QLabel(
                        f"<b style='color:#a6e3a1'>{role.upper()}</b>"
                        f"<span style='color:#6c7086'> → </span>{h}"
                    )
                    self.special_inner.addWidget(lbl)
                    break

        # Auto-detect ID columns and their paired price columns
        self._id_columns = find_id_columns(self.headers)
        for id_info in self._id_columns:
            assigned.add(id_info["id_col"])
            if id_info["base_price_col"]:
                assigned.add(id_info["base_price_col"])
            if id_info["ab_price_col"]:
                assigned.add(id_info["ab_price_col"])

            bp = id_info["base_price_col"] or "—"
            ap = id_info["ab_price_col"] or "—"
            lbl = QLabel(
                f"<b style='color:#89b4fa'>ID [{id_info['prefix']}]</b>"
                f"<span style='color:#6c7086'> → </span>{id_info['id_col']}"
                f"  <span style='color:#6c7086'>base:</span> {bp}"
                f"  <span style='color:#6c7086'>ab:</span> {ap}"
            )
            self.special_inner.addWidget(lbl)

        if not self.special_cols and not self._id_columns:
            self.special_inner.addWidget(
                QLabel("(none auto-detected — rename columns to match expected names)")
            )

        # Attribute checkboxes (all columns not already assigned)
        for h in self.headers:
            if not h or h in assigned:
                continue
            cb = QCheckBox(h)
            cb.setChecked(h in ATTR_COLUMN_MAP)
            self.col_checkboxes[h] = cb
            self.var_layout.addWidget(cb)

        self.var_layout.addStretch()

    def get_config(self):
        """
        Returns (special_cols, id_columns, selected_var_cols).

        special_cols      – dict with "name" and "category" column names
        id_columns        – list of dicts from find_id_columns()
        selected_var_cols – list of (col_name, attr_slug) for checked attribute columns
        """
        selected = []
        for col_name, cb in self.col_checkboxes.items():
            if cb.isChecked():
                slug = ATTR_COLUMN_MAP.get(col_name) or excel_value_to_slug(col_name) or col_name.lower()
                selected.append((col_name, slug))
        return self.special_cols, self._id_columns, selected
