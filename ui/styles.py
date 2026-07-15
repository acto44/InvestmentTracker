# ── Design tokens (session 10 "restrained fintech" pass) ─────────────────────
# Direction: Linear/Mercury/Stripe — dense but calm. Rules the whole UI
# follows (and future sessions must keep):
#   SPACING  4/8px scale only: 4 8 12 16 20 24 32. Card padding = 20px.
#   SURFACES exactly four elevation levels (BG → CARD → CARD_ALT → HOVER),
#            flat colors, no gradients.
#   COLOR    ONE accent (indigo #6C7FF2) for interactive/selected things.
#            Semantic colors carry MEANING only: green = gains,
#            red = losses, amber = warnings. Nothing is colored for
#            decoration; neutral data is TEXT/MUTED.
#   BORDERS  one treatment: 1px rgba(148,163,184,0.12) hairline
#            (BORDER is its hex twin for matplotlib spines).
#   RADIUS   10px for every card/container/control; 6px for small inner
#            items (menu entries, pills, tags). No other radii.
#   TYPE     Inter (falls back to Segoe UI on machines without it).
#            Scale: 8pt uppercase +8% letter-spaced labels (set via
#            QFont, QSS can't letter-space) · 9pt small · 10pt body ·
#            15/18pt DemiBold numbers. Numeric columns right-aligned.

FONT_STACK = "'Inter', 'Segoe UI Variable Text', 'Segoe UI', sans-serif"

# spacing scale (px)
SP1, SP2, SP3, SP4, SP5, SP6, SP8 = 4, 8, 12, 16, 20, 24, 32
CARD_PAD = 20
RADIUS = 10
RADIUS_SM = 6

# ── surfaces: four elevation levels, flat ────────────────────────────────────
BG        = "#0B0F1A"       # 0 · window
CARD      = "#111726"       # 1 · panels, cards, tables
CARD_ALT  = "#161D30"       # 2 · alternate rows, nested surfaces
HOVER     = "#1C2438"       # 3 · hover / pressed surfaces
INPUT_BG  = "#0D1220"       # fields sit just below card level
BG_TOP    = BG              # compat (the gradient is retired — flat)

TEXT      = "#E6EAF3"
MUTED     = "#8B96AD"       # neutral slate (not blue-tinted)
FAINT     = "#5C6880"       # de-emphasized meta text

BORDER    = "#1E2536"       # hex twin of BORDER_SOFT (matplotlib needs hex)
BORDER_SOFT    = "rgba(148,163,184,0.12)"
BORDER_SOFT_HI = "rgba(148,163,184,0.24)"

# ── the ONE accent ───────────────────────────────────────────────────────────
ACCENT        = "#6C7FF2"
ACCENT_HOVER  = "#7F90F5"
ACCENT_ACTIVE = "#5A6BD9"
ACCENT_LITE   = "#1A2138"   # accent-tinted selection surface

# compat aliases — the session-9 gradient is retired; primary actions are
# flat accent now. Kept so no widget import breaks.
GRAD_A = GRAD_B = GRADIENT = ACCENT

# ── semantic colors: meaning only ────────────────────────────────────────────
GREEN     = "#34D399"       # gains
RED       = "#F87171"       # losses
AMBER     = "#FBBF24"       # warnings

HEADER_BG = "#0D1220"       # toolbar / menu bar / status bar
HEADER_FG = "#C3CBDD"

# Soft tinted backgrounds (row highlights, badges, callouts)
GREEN_SOFT = "#0F2A1F"
RED_SOFT   = "#2C1820"
AMBER_SOFT = "#2A2110"

# Informational callout (dashboard "since last update")
INFO_BG     = "#131B2E"
INFO_BORDER = "#243250"
INFO_TEXT   = "#9DB4E8"

# Warning callout ("no valuation set" hint)
WARN_BG     = "#2A2110"
WARN_BORDER = "#57431A"
WARN_TEXT   = "#FCD34D"

# Soft secondary buttons (e.g. "Open website", "Edit", "Open")
SOFT_BTN_BG     = "#161D30"
SOFT_BTN_BORDER = "#28324B"
SOFT_BTN_TEXT   = "#AAB6D4"
SOFT_BTN_HOVER  = "#1C2438"

# Semantic company-status colors (used by tree, dashboard, compare)
STATUS_ACTIVE   = GREEN
STATUS_EXITED   = MUTED
STATUS_BANKRUPT = RED

QSS = f"""
QMainWindow, QDialog {{
    background: {BG};
}}
QWidget {{
    font-family: {FONT_STACK};
    font-size: 10pt;
    color: {TEXT};
}}
QLabel {{ background: transparent; }}
/* ── Tabs: segmented pills ── */
QTabWidget {{ background: transparent; }}
QTabBar {{ background: transparent; border: none; }}
QTabWidget::pane {{
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS}px;
    background: {BG};
    top: 4px;
    padding: 2px;
}}
QTabBar::tab {{
    background: transparent;
    color: {MUTED};
    font-weight: 600;
    padding: 8px 16px;
    border-radius: {RADIUS_SM}px;
    margin: 0 4px 8px 0;
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
    border-radius: {RADIUS}px;
    alternate-background-color: transparent;
    outline: none;
    padding: 8px;
}}
QTreeWidget::item {{
    padding: 6px 4px;
    border-radius: {RADIUS_SM}px;
}}
QTreeWidget::item:selected {{
    background: {ACCENT_LITE};
    color: {ACCENT};
}}
QTreeWidget::item:hover:!selected {{
    background: {HOVER};
}}
/* ── Buttons: flat accent = primary action ── */
QPushButton {{
    background: {ACCENT};
    color: #FFFFFF;
    border: none;
    padding: 8px 16px;
    border-radius: {RADIUS_SM}px;
    font-weight: 600;
}}
QPushButton:hover   {{ background: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background: {ACCENT_ACTIVE}; }}
QPushButton:disabled {{
    background: {CARD_ALT};
    color: {FAINT};
}}
/* ── Inputs ── */
QLineEdit, QTextEdit, QComboBox, QDateEdit,
QDoubleSpinBox, QSpinBox, QPlainTextEdit {{
    background: {INPUT_BG};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS_SM}px;
    padding: 8px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
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
    color: {FAINT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: {RADIUS_SM}px;
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
    border-radius: {RADIUS}px;
    margin-top: 16px;
    padding-top: 8px;
    font-weight: 600;
    background: {CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: {MUTED};
}}
/* ── Table ── */
QHeaderView::section {{
    background: transparent;
    color: {MUTED};
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    font-weight: 600;
    font-size: 8pt;
}}
QTableWidget, QTableView {{
    background: {CARD};
    alternate-background-color: {CARD_ALT};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS}px;
    gridline-color: transparent;
    color: {TEXT};
    padding: 4px;
}}
QTableWidget::item, QTableView::item {{
    padding: 4px 8px;
    border-radius: {RADIUS_SM}px;
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background: {HOVER};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {ACCENT_LITE};
    color: {TEXT};
}}
QTableCornerButton::section {{ background: transparent; border: none; }}
/* ── Menus ── */
QMenuBar {{
    background: {HEADER_BG};
    color: {HEADER_FG};
    padding: 4px;
    border-bottom: 1px solid {BORDER_SOFT};
}}
QMenuBar::item {{ padding: 6px 12px; border-radius: {RADIUS_SM}px; }}
QMenuBar::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: {RADIUS}px;
    padding: 6px;
}}
QMenu::item {{ padding: 8px 24px; border-radius: {RADIUS_SM}px; }}
QMenu::item:selected {{ background: {ACCENT_LITE}; color: {ACCENT}; }}
QMenu::separator {{ height: 1px; background: {BORDER_SOFT}; margin: 6px 8px; }}
/* ── Scroll areas: kill the default white viewport ── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollArea QWidget#qt_scrollarea_viewport {{ background: transparent; }}
/* ── Scrollbars: slim, neutral, barely-there ── */
QScrollBar:vertical {{
    border: none; background: transparent; width: 8px; margin: 4px;
}}
QScrollBar::handle:vertical {{
    background: rgba(148,163,184,0.22); border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(148,163,184,0.40); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    border: none; background: transparent; height: 8px; margin: 4px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(148,163,184,0.22); border-radius: 4px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: rgba(148,163,184,0.40); }}
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
    border-radius: {RADIUS_SM}px;
    padding: 8px 12px;
    font-size: 9pt;
    font-weight: normal;
}}
/* ── Toolbar ── */
QToolBar {{
    background: {HEADER_BG};
    border: none;
    border-bottom: 1px solid {BORDER_SOFT};
    padding: 8px 12px;
    spacing: 4px;
}}
QToolBar::separator {{
    background: {BORDER_SOFT};
    width: 1px;
    margin: 8px 8px;
}}
QToolButton {{
    background: transparent;
    color: {HEADER_FG};
    border: none;
    border-radius: {RADIUS_SM}px;
    padding: 8px 12px;
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
    width: 16px;
    height: 16px;
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: {RADIUS_SM}px;
    background: {INPUT_BG};
}}
QCheckBox::indicator:hover   {{ border-color: {ACCENT}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
/* ── Radio buttons ── */
QRadioButton {{ background: transparent; spacing: 8px; }}
QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER_SOFT_HI};
    border-radius: 8px;
    background: {INPUT_BG};
}}
QRadioButton::indicator:hover   {{ border-color: {ACCENT}; }}
QRadioButton::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
/* ── List widgets (quick jump etc.) ── */
QListWidget {{
    background: {CARD};
    border: 1px solid {BORDER_SOFT};
    border-radius: {RADIUS}px;
    outline: none;
    padding: 4px;
}}
QListWidget::item {{
    padding: 8px 12px;
    border-radius: {RADIUS_SM}px;
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


def label_font(base: 'object' = None):
    """The 8pt uppercase micro-label font with +8% letter-spacing —
    QSS cannot letter-space, so label widgets call this."""
    from PyQt6.QtGui import QFont
    f = QFont()
    f.setPointSize(8)
    f.setWeight(QFont.Weight.DemiBold)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
    return f
