"""Step 4 — Run validation (progress bar + live log)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit,
)
from PySide6.QtGui import QFont


class Step4(QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 28, 40, 28)

        title = QLabel("Step 4 — Run Validation")
        title.setObjectName("step_title")
        layout.addWidget(title)

        # Start/Stop buttons live in the nav bar (see MainWindow).
        self.btn_start = QPushButton("▶  Start Validation")
        self.btn_start.setFixedHeight(38)
        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setProperty("danger", True)
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_lbl = QLabel("Ready.")
        self.status_lbl.setStyleSheet("color: #a6adc8;")
        layout.addWidget(self.status_lbl)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log, stretch=1)

    def append_log(self, msg):
        self.log.append(msg)
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_progress(self, current, total):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.status_lbl.setText(f"Processing {current} / {total}…")
