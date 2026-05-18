"""Full-window loading overlay with animated spinner."""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRectF, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QFont


class LoadingOverlay(QWidget):
    """
    Semi-transparent overlay that covers its parent widget entirely.
    Shows an animated spinning arc and a status line.

    Usage:
        overlay.start("Validating Excel file…")
        overlay.stop()
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        self._angle = 0
        self._text  = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    # ── public API ───────────────────────────────────────────────────────────

    def start(self, text: str = "Please wait…"):
        self._text = text
        self._fit()
        self.raise_()
        self.show()
        self._timer.start(16)   # ~60 fps

    def stop(self):
        self._timer.stop()
        self.hide()

    def set_text(self, text: str):
        self._text = text
        self.update()

    # ── internal ─────────────────────────────────────────────────────────────

    def _fit(self):
        if self.parent():
            self.setGeometry(self.parent().rect())

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark, slightly transparent background
        p.fillRect(self.rect(), QColor(17, 17, 27, 215))

        cx = self.width()  // 2
        cy = self.height() // 2
        r  = 34

        spinner_rect = QRectF(cx - r, cy - r - 18, r * 2, r * 2)

        # Background ring
        ring_pen = QPen(QColor(49, 50, 68), 5)
        ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(ring_pen)
        p.drawEllipse(spinner_rect)

        # Spinning arc
        arc_pen = QPen(QColor("#89b4fa"), 5)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(spinner_rect.toRect(), -self._angle * 16, 110 * 16)

        # Status text
        p.setPen(QColor("#cdd6f4"))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(
            QRect(cx - 260, cy + 28, 520, 36),
            Qt.AlignmentFlag.AlignCenter,
            self._text,
        )

        p.end()
