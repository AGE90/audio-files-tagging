"""
QSS Stylesheets for the GUI application.

Defines consistent styling across the application using Qt Style Sheets.
"""

# Main application stylesheet - Dark Theme
MAIN_STYLESHEET = """
QMainWindow {
    background-color: #1e1e1e;
    color: #e0e0e0;
}

QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
}

QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: 1px solid #0e639c;
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 13px;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1177bb;
    border: 1px solid #1177bb;
}

QPushButton:pressed {
    background-color: #0d5689;
}

QPushButton:disabled {
    background-color: #3c3c3c;
    color: #7f7f7f;
    border: 1px solid #3c3c3c;
}

QLabel {
    color: #e0e0e0;
    background-color: transparent;
}

QLabel[heading="true"] {
    font-size: 16px;
    font-weight: bold;
    color: #4ec9b0;
    padding: 10px 0;
}

QTableWidget {
    background-color: #252526;
    alternate-background-color: #2d2d30;
    color: #e0e0e0;
    border: 1px solid #3e3e42;
    gridline-color: #3e3e42;
    selection-background-color: #094771;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 5px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #2d2d30;
    border: none;
    border-bottom: 2px solid #0e639c;
    border-right: 1px solid #3e3e42;
    padding: 8px;
    font-weight: bold;
    color: #cccccc;
}

QHeaderView::section:hover {
    background-color: #3e3e42;
}

QLineEdit, QSpinBox, QTextEdit {
    background-color: #3c3c3c;
    color: #e0e0e0;
    border: 1px solid #5a5a5a;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #094771;
    selection-color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border: 2px solid #0e639c;
    background-color: #2d2d30;
}

QLineEdit:disabled, QSpinBox:disabled, QTextEdit:disabled {
    background-color: #2d2d30;
    color: #7f7f7f;
    border: 1px solid #3e3e42;
}

QCheckBox {
    spacing: 8px;
    color: #e0e0e0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #5a5a5a;
    border-radius: 3px;
    background-color: #3c3c3c;
}

QCheckBox::indicator:hover {
    border: 2px solid #0e639c;
}

QCheckBox::indicator:checked {
    background-color: #0e639c;
    border-color: #0e639c;
    image: url(none);
}

QCheckBox:disabled {
    color: #7f7f7f;
}

QProgressBar {
    border: 1px solid #5a5a5a;
    border-radius: 4px;
    text-align: center;
    background-color: #3c3c3c;
    color: #e0e0e0;
}

QProgressBar::chunk {
    background-color: #0e639c;
    border-radius: 3px;
}

QTabWidget::pane {
    border: 1px solid #3e3e42;
    background-color: #1e1e1e;
    border-radius: 4px;
    top: -1px;
}

QTabBar::tab {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-bottom: none;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #cccccc;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    border-bottom: 2px solid #0e639c;
    color: #ffffff;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #3e3e42;
}

QStatusBar {
    background-color: #007acc;
    border-top: 1px solid #0e639c;
    color: #ffffff;
}

QMenuBar {
    background-color: #2d2d30;
    border-bottom: 1px solid #3e3e42;
    color: #e0e0e0;
}

QMenuBar::item {
    padding: 6px 12px;
    background-color: transparent;
}

QMenuBar::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QMenu {
    background-color: #252526;
    border: 1px solid #3e3e42;
    color: #e0e0e0;
}

QMenu::item {
    padding: 6px 30px 6px 20px;
}

QMenu::item:selected {
    background-color: #094771;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #3e3e42;
    margin: 4px 0px;
}

QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 14px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 7px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4e4e4e;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1e1e1e;
    height: 14px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #424242;
    border-radius: 7px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4e4e4e;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

# Success/Error message styles (Dark theme compatible)
SUCCESS_STYLE = "color: #4ec9b0; font-weight: bold;"
ERROR_STYLE = "color: #f48771; font-weight: bold;"
WARNING_STYLE = "color: #dcdcaa; font-weight: bold;"
INFO_STYLE = "color: #9cdcfe; font-weight: bold;"


def get_status_style(status_type: str) -> str:
    """
    Get the appropriate style for status messages.
    
    Parameters
    ----------
    status_type : str
        One of: 'success', 'error', 'warning', 'info'
    
    Returns
    -------
    str
        QSS style string
    """
    styles = {
        'success': SUCCESS_STYLE,
        'error': ERROR_STYLE,
        'warning': WARNING_STYLE,
        'info': INFO_STYLE,
    }
    return styles.get(status_type, INFO_STYLE)
