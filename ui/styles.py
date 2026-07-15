# ── "Soft deep-space" design system (session 9 SUPERDESIGN pass) ─────────────
# Design spec lives in .superdesign/design_iterations/tracker_theme_1.html
# (gitignored). Soft indigo-black surfaces, hairline alpha borders, one
# electric blue→violet gradient for primary actions, pill tabs, generous
# radii. Every widget styles through THESE tokens — no stray hexes.

ACCENT        = "#7C93FF"   # soft periwinkle — links, active states, titles
ACCENT_HOVER  = "#93A7FF"
ACCENT_ACTIVE = "#6478E8"
ACCENT_LITE   = "#1A2340"   # accent-tinted surface (badges, selection)

GRAD_A        = "#4E6EF2"   # primary-button gradient: electric blue →
GRAD_B        = "#7A5AF8"   # → violet
GRAD_A_HOVER  = "#5D7BFF"
GRAD_B_HOVER  = "#8A6CFF"
GRAD_A_DOWN   = "#4460D9"
GRAD_B_DOWN   = "#6A4CE0"

BG        = "#070B16"       # window base (near-black indigo)
BG_TOP    = "#0B1226"       # gradient top
CARD      = "#101830"       # raised surface
CARD_ALT  = "#16203C"       # alternate rows / gradient start
HOVER     = "#1A2542"       # hover surface
INPUT_BG  = "#0D1428"       # fields sit slightly below the cards
TEXT      = "#EAEFFC"
MUTED     = "#8CA0C8"
BORDER    = "#22304F"       # hex twin of BORDER_SOFT (matplotlib needs hex)

# hairline alpha borders — the "soft" in soft deep-space
BORDER_SOFT    = "rgba(124,147,255,0.14)"
BORDER_SOFT_HI = "rgba(124,147,255,0.30)"

GREEN     = "#4ADE80"
RED       = "#FB7185"       # softer rose than the old #F87171
AMBER     = "#FBBF24"

HEADER_BG = "#0C1224"       # toolbar / menu bar / status bar
HEADER_FG = "#C6D2F0"

# Soft tinted backgrounds (row highlights, badges, callouts)
GREEN_SOFT = "#0F2A1D"
RED_SOFT   = "#2C1620"
AMBER_SOFT = "#2A2110"

# Informational callout (dashboard "since last update")
INFO_BG     = "#0F2036"
INFO_BORDER = "#1E3A5F"
INFO_TEXT   = "#7DD3FC"

# Warning callout ("no valuation set" hint)
WARN_BG     = "#2A2110"
WARN_BORDER = "#57431A"
WARN_TEXT   = "#FCD34D"

# Soft secondary buttons (e.g. "Open website", "Edit", "Open")
SOFT_BTN_BG     = "#1A2340"
SOFT_BTN_BORDER = "#2A3A66"
SOFT_BTN_TEXT   = "#9FB2FF"
SOFT_BTN_HOVER  = "#22305A"

# Semantic company-status colors (used by tree, dashboard, compare)
STATUS_ACTIVE   = GREEN
STATUS_EXITED   = MUTED
STATUS_BANKRUPT = RED

# The one primary-action gradient, reused anywhere a widget needs it inline
GRADIENT = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {GRAD_A}, stop:1 {GRAD_B})")
_GRADIENT_HOVER = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                   f"stop:0 {GRAD_A_HOVER}, stop:1 {GRAD_B_HOVER})")
_GRADIENT_DOWN = (f"qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                  f"stop:0 {GRAD_A_DOWN}, stop:1 {GRAD_B_DOWN})")
_BG_GRADIENT = (f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                f"stop:0 {BG_TOP}, stop:1 {BG})")

QSS = f"""
QMainWindow, QDialog {{
    background: {_BG_GRADIENT};
}}
QWidget {{
    font-family: 'Segoe UI Variable Text', 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QLabel {{ background: transparent; }}
/* ── Tabs: segmented pills ── */
QTabWidget {{ background: transparent; }}
QTabBar {{ background: transparent; border: none; }}
QTabWidget::pane {{
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    background: {BG};
    top: 6px;
    padding: 2px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    font-weight: 600;
    padding: 7px 18px;
    border-radius: 8px;
    margin: 2px 3px 8px 0;
}}
QTabBar::tab:selected {{
    background: {ACCENT_LITE};
    color: {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    background: {HOVER};
    color: {TEXT};
}}
/* ── Tree ── */
QTreeWidget {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    alternate-background-color: transparent;
    outline: none;
    padding: 6px;
}}
QTreeWidget::item {{
    padding: 6px 4px;
    border-radius: 7px;
}}
QTreeWidget::item:selected {{
    background: {ACCENT_LITE};
    color: {ACCENT};
}}
QTreeWidget::item:hover:!selected {{
    background: {HOVER};
}}
/* ── Buttons: THE gradient = primary action ── */
QPushButton {{
    background: {GRADIENT};
    color: #FFFFFF;
    border: none;
    padding: 8px 18px;
    border-radius: 9px;
    font-weight: bold;
}}
QPushButton:hover   {{ background: {_GRADIENT_HOVER}; }}
QPushButton:pressed {{ background: {_GRADIENT_DOWN}; }}
QPushButton:disabled {{
    background: {CARD_ALT};
    color: {MUTED};
}}
/* ── Inputs ── */
QLineEdit, QTextEdit, QComboBox, QDateEdit,
QDoubleSpinBox, QSpinBox, QPlainTextEdit {{
    background: {INPUT_BG};
    border: 1px solid {BORDER_SOFT};
    border-radius: 9px;
    padding: 7px 12px;
    color: {TEXT};
    selection-background-color: {GRAD_A};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateEdit:focus,
QDoubleSpinBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT};
    background: {CARD_ALT};
}}
QLineEdit:disabled, QComboBox:disabled, QDoubleSpinBox:disabled,
QSpinBox:disabled, QDateEdit:disabled, QTextEdit:disabled {{
    background: transparent;
    color: {MUTED};
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 9px;
    padding: 4px;
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
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    margin-top: 16px;
    padding-top: 8px;
    font-weight: bold;
    background: {CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: {ACCENT};
}}
/* ── Table ── */
QHeaderView::section {{
    background: transparent;
    color: {MUTED};
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    font-weight: bold;
    font-size: 8.5pt;
}}
QTableWidget {{
    background: {CARD};
    alternate-background-color: {CARD_ALT};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    gridline-color: transparent;
    color: {TEXT};
    padding: 4px;
}}
QTableWidget::item {{
    padding: 4px 6px;
    border-radius: 5px;
}}
QTableWidget::item:selected {{
    background: {ACCENT_LITE};
    color: {TEXT};
}}
QTableCornerButton::section {{ background: transparent; border: none; }}
/* ── Menus ── */
QMenuBar {{
    background: {HEADER_BG};
    color: {HEADER_FG};
    padding: 3px;
    border-bottom: 1px solid {BORDER_SOFT};
}}
QMenuBar::item {{ padding: 6px 13px; border-radius: 7px; }}
QMenuBar::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 26px; border-radius: 7px; }}
QMenu::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {BORDER_SOFT}; margin: 6px 8px; }}
/* ── Scroll areas: kill the default white viewport ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea QWidget#qt_scrollarea_viewport {{ background: transparent; }}
/* ── Scrollbars: slim, rounded, barely-there ── */
QScrollBar:vertical {{
    border: none; background: transparent; width: 8px; margin: 3px;
}}
QScrollBar::handle:vertical {{
    background: rgba(124,147,255,0.25); border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(124,147,255,0.45); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    border: none; background: transparent; height: 8px; margin: 3px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(124,147,255,0.25); border-radius: 4px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: rgba(124,147,255,0.45); }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
/* ── Splitter ── */
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 3px; }}
/* ── Status bar ── */
QStatusBar {{
    background: {HEADER_BG};
    color: {MUTED};
    font-size: 9pt;
    border-top: 1px solid {BORDER_SOFT};
}}
/* ── Dialog button box ── */
QDialogButtonBox QPushButton {{ min-width: 92px; }}
/* ── Tooltips ── */
QToolTip {{
    background: {CARD_ALT};
    color: {TEXT};
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 8px;
    padding: 9px 13px;
    font-size: 9pt;
    font-weight: normal;
}}
/* ── Toolbar ── */
QToolBar {{
    background: {HEADER_BG};
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    padding: 8px 10px;
    spacing: 6px;
}}
QToolBar::separator {{
    background: {BORDER_SOFT};
    width: 1px;
    margin: 7px 7px;
}}
QToolButton {{
    background: transparent;
    color: {HEADER_FG};
    border: none;
    border-radius: 9px;
    padding: 8px 14px;
    font-weight: 600;
    font-size: 9.5pt;
}}
QToolButton:hover  {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QToolButton:pressed {{ background: {HOVER}; color: {ACCENT}; }}
/* ── Check boxes ── */
QCheckBox {{
    spacing: 8px;
    padding: 2px 0;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 5px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:hover   {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {GRADIENT}; border-color: {GRAD_A}; }}
/* ── Radio buttons ── */
QRadioButton {{ background: transparent; spacing: 8px; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 8px;
    background: {INPUT_BG};
}}
QRadioButton::indicator:hover   {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{ background: {GRADIENT}; border-color: {GRAD_A}; }}
/* ── List widgets (quick jump etc.) ── */
QListWidget {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: 12px;
    outline: none;
    padding: 5px;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: 7px;
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
    selection-background-color: {GRAD_A};
    selection-color: #FFFFFF;
}}
"""
