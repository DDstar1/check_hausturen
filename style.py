STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
}
QPushButton:hover { background-color: #b4d0ff; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
QPushButton[danger="true"] { background-color: #f38ba8; }
QLineEdit, QComboBox, QTextEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 5px 8px;
    color: #cdd6f4;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #313244;
    selection-background-color: #45475a;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; color: #89b4fa; }
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    height: 22px;
    color: #cdd6f4;
}
QProgressBar::chunk { background-color: #89b4fa; border-radius: 3px; }
QTableWidget {
    background-color: #181825;
    gridline-color: #313244;
    border: none;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background-color: #45475a; }
QHeaderView::section {
    background-color: #313244;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #45475a;
    font-weight: bold;
    color: #cdd6f4;
}
QScrollBar:vertical { background: #181825; width: 10px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #45475a; border-radius: 5px; min-height: 20px; }
QScrollBar:horizontal { background: #181825; height: 10px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: #45475a; border-radius: 5px; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 3px;
    border: 1px solid #6c7086;
    background: #313244;
}
QCheckBox::indicator:checked { background: #89b4fa; border-color: #89b4fa; }
QListWidget {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
}
QLabel#step_title { font-size: 18px; font-weight: bold; color: #89b4fa; }
QLabel#step_sub   { color: #a6adc8; font-size: 12px; }
QFrame#nav_bar    { background-color: #181825; border-top: 1px solid #313244; }
"""
