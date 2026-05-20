"""Mode selector — first screen the user sees."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea
from PySide6.QtCore import Signal, Qt


class StepMode(QWidget):
    mode_chosen = Signal(str)

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setSpacing(16)
        layout.setContentsMargins(80, 60, 80, 60)

        title = QLabel("check_hastur")
        title.setObjectName("step_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("What would you like to do?")
        sub.setObjectName("step_sub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)
        layout.addSpacing(24)

        for label, desc, mode in [
            ("Check Masterlist",
             "Validate each product in your Excel masterlist against the WooCommerce API.",
             "check_masterlist"),
            ("Find Missing Products",
             "Find missing products between a WooCommerce category and your Excel masterlist.",
             "compare_category"),
            ("Set Products",
             "Update prices and attributes on WooCommerce products one by one, with confirmation after each.",
             "set_products"),
        ]:
            btn = QPushButton(f"{label}\n{desc}")
            btn.setFixedHeight(80)
            btn.setStyleSheet("text-align: left; padding: 12px 16px;")
            btn.clicked.connect(lambda _=False, m=mode: self.mode_chosen.emit(m))
            layout.addWidget(btn)

        layout.addStretch()
