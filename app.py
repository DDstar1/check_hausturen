"""check_hastur — entry point."""

import sys
from PySide6.QtWidgets import QApplication
from main_window import MainWindow
from style import STYLE

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.setStyleSheet(STYLE)
    win.show()
    sys.exit(app.exec())
