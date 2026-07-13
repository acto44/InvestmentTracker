# ── Dark "fintech" palette ────────────────────────────────────────────────────
# Deep-navy surfaces, bright accent blue, luminous green/red for gains/losses.

ACCENT        = "#3B82F6"   # bright blue
ACCENT_HOVER  = "#2563EB"
ACCENT_ACTIVE = "#1D4ED8"
ACCENT_LITE   = "#1C2A45"   # subtle accent-tinted surface

BG        = "#0B1220"       # window background (deep navy)
CARD      = "#141D2E"       # raised surface
CARD_ALT  = "#18233A"       # alternate table rows
HOVER     = "#1D2A42"       # hover surface
TEXT      = "#E6EDF7"
MUTED     = "#8CA3C4"
BORDER    = "#243450"

GREEN     = "#4ADE80"
RED       = "#F87171"
AMBER     = "#FBBF24"

HEADER_BG = "#0D1526"       # table headers / menu bar
HEADER_FG = "#C9D6EA"

# Soft tinted backgrounds (row highlights, badges, callouts)
GREEN_SOFT = "#12291C"
RED_SOFT   = "#2C181C"
AMBER_SOFT = "#2A2110"

# Informational callout (dashboard "since last update")
INFO_BG     = "#10233B"
INFO_BORDER = "#1E3A5F"
INFO_TEXT   = "#7DD3FC"

# Warning callout ("no valuation set" hint)
WARN_BG     = "#2A2110"
WARN_BORDER = "#57431A"
WARN_TEXT   = "#FCD34D"

# Soft secondary buttons (e.g. "Open website", "Edit", "Open")
SOFT_BTN_BG     = "#1C2A45"
SOFT_BTN_BORDER = "#2B4066"
SOFT_BTN_TEXT   = "#7EB0FA"
SOFT_BTN_HOVER  = "#233657"

# Semantic company-status colors (used by tree, dashboard, compare)
STATUS_ACTIVE   = GREEN
STATUS_EXITED   = MUTED
STATUS_BANKRUPT = RED

QSS = f"""
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QLabel {{ background: transparent; }}
/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {BG};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    padding: 9px 22px;
    border: 1px solid transparent;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    font-weight: bold;
    border-bottom: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    border-bottom: 2px solid {BORDER};
}}
/* ── Tree ── */
QTreeWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    alternate-background-color: {CARD_ALT};
    outline: none;
}}
QTreeWidget::item {{
    padding: 5px 2px;
    border-radius: 4px;
}}
QTreeWidget::item:selected {{
    background: {ACCENT_LITE};
    color: {ACCENT};
}}
QTreeWidget::item:hover:!selected {{
    background: {HOVER};
}}
/* ── Buttons ── */
QPushButton {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    padding: 7px 16px;
    border-radius: 7px;
    font-weight: bold;
}}
QPushButton:hover   {{ background: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background: {ACCENT_ACTIVE}; }}
QPushButton:disabled {{
    background: {BORDER};
    color: {MUTED};
}}
/* ── Inputs ── */
QLineEdit, QTextEdit, QComboBox, QDateEdit,
QDoubleSpinBox, QSpinBox, QPlainTextEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 10px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
    background: {CARD_ALT};
}}
QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled,
QSpinBox:disabled, QDateEdit:disabled, QTextEdit:disabled {{
    background: {BG};
    color: {MUTED};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {ACCENT_LITE};
    selection-color: {ACCENT};
    outline: none;
}}
QDoubleSpinBox::up-button, QSpinBox::up-button, QDateEdit::up-button,
QDoubleSpinBox::down-button, QSpinBox::down-button, QDateEdit::down-button {{
    background: {HOVER};
    border: none;
    width: 18px;
}}
/* ── Group box ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 6px;
    font-weight: bold;
    background: {CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT};
}}
/* ── Table ── */
QHeaderView::section {{
    background: {HEADER_BG};
    color: {HEADER_FG};
    padding: 7px 8px;
    border: none;
    font-weight: bold;
    font-size: 9pt;
}}
QTableWidget {{
    background: {CARD};
    alternate-background-color: {CARD_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    color: {TEXT};
}}
QTableWidget::item:selected {{
    background: {ACCENT_LITE};
    color: {TEXT};
}}
QTableCornerButton::section {{ background: {HEADER_BG}; border: none; }}
/* ── Menus ── */
QMenuBar {{
    background: {HEADER_BG};
    color: {HEADER_FG};
    padding: 2px;
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item {{ padding: 5px 12px; border-radius: 5px; }}
QMenuBar::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 6px; }}
/* ── Scroll areas: kill the default white viewport ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea QWidget#qt_scrollarea_viewport {{ background: transparent; }}
/* ── Scrollbars ── */
QScrollBar:vertical {{
    border: none; background: transparent; width: 9px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: #33486B; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    border: none; background: transparent; height: 9px; margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 4px; min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: #33486B; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
/* ── Splitter ── */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
/* ── Status bar ── */
QStatusBar {{
    background: {HEADER_BG};
    color: {MUTED};
    font-size: 9pt;
    border-top: 1px solid {BORDER};
}}
/* ── Dialog button box ── */
QDialogButtonBox QPushButton {{ min-width: 80px; }}
/* ── Tooltips ── */
QToolTip {{
    background: {CARD_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 9pt;
    font-weight: normal;
}}
/* ── Toolbar ── */
QToolBar {{
    background: {HEADER_BG};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 5px 8px;
    spacing: 4px;
}}
QToolBar::separator {{
    background: {BORDER};
    width: 1px;
    margin: 6px 6px;
}}
QToolButton {{
    background: transparent;
    color: {HEADER_FG};
    border: none;
    border-radius: 7px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 9pt;
}}
QToolButton:hover  {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QToolButton:pressed {{ background: {HOVER}; color: {ACCENT}; }}
/* ── Check boxes ── */
QCheckBox {{
    spacing: 7px;
    padding: 2px 0;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {CARD};
}}
QCheckBox::indicator:hover   {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
/* ── Radio buttons ── */
QRadioButton {{ background: transparent; spacing: 7px; }}
QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD};
}}
QRadioButton::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
/* ── List widgets (quick jump etc.) ── */
QListWidget {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 6px;
    color: {TEXT};
}}
QListWidget::item:hover    {{ background: {HOVER}; }}
QListWidget::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
/* ── Message boxes ── */
QMessageBox {{ background: {CARD}; }}
/* ── Calendar popup ── */
QCalendarWidget QWidget {{ background: {CARD}; }}
QCalendarWidget QAbstractItemView {{
    background: {CARD};
    selection-background-color: {ACCENT};
    selection-color: #FFFFFF;
}}
"""
