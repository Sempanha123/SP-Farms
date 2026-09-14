from dataclasses import dataclass
from enum import StrEnum


class ThemeMode(StrEnum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True, slots=True)
class ThemePalette:
    window: str
    surface: str
    surface_alt: str
    border: str
    text: str
    muted_text: str
    accent: str
    accent_hover: str
    accent_text: str
    warning: str
    danger: str
    success: str
    info: str
    selection: str


LIGHT_PALETTE = ThemePalette(
    window="#F3F4F1",
    surface="#FFFFFF",
    surface_alt="#E9ECE8",
    border="#C9CEC8",
    text="#171B18",
    muted_text="#606861",
    accent="#F2C313",
    accent_hover="#FFD52A",
    accent_text="#16160F",
    warning="#D99A16",
    danger="#D94D52",
    success="#24B968",
    info="#2877DF",
    selection="#FFF1A8",
)

DARK_PALETTE = ThemePalette(
    window="#0D1113",
    surface="#121719",
    surface_alt="#181E21",
    border="#343C40",
    text="#F1F3F3",
    muted_text="#9AA3A7",
    accent="#F4C915",
    accent_hover="#FFD82D",
    accent_text="#15160F",
    warning="#E5A627",
    danger="#F05D63",
    success="#25D06F",
    info="#2F7BEA",
    selection="#34341C",
)


def palette(mode: ThemeMode) -> ThemePalette:
    return LIGHT_PALETTE if mode is ThemeMode.LIGHT else DARK_PALETTE


def style_sheet(mode: ThemeMode) -> str:
    colors = palette(mode)
    return f"""
QWidget {{
    background: {colors.window};
    color: {colors.text};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 12px;
}}
QFrame[panel="true"], QDialog {{
    background: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 5px;
}}
QLabel {{ background: transparent; border: 0; }}
QLabel[muted="true"] {{ color: {colors.muted_text}; }}
QLabel[heading="true"] {{ font-size: 15px; font-weight: 700; }}
QLabel[metricValue="true"] {{ font-size: 17px; font-weight: 750; }}
QLabel#brand {{ font-size: 20px; font-weight: 800; }}
QLabel#brandVersion, QLabel#brandSubtitle {{ color: {colors.muted_text}; }}
QLabel#brandSubtitle {{ font-size: 10px; }}
QWidget#topNavigation {{
    background: #101518;
    border-bottom: 1px solid {colors.border};
}}
QWidget#brandBlock {{ background: transparent; }}
QLabel#brandMark {{
    color: {colors.accent_text};
    background: #37BE67;
    border-radius: 5px;
    font-size: 20px;
    font-weight: 900;
}}
QPushButton {{
    min-height: 27px;
    padding: 0 10px;
    border: 1px solid {colors.border};
    border-radius: 4px;
    background: {colors.surface_alt};
}}
QPushButton:hover {{ border-color: #596267; background: #20272A; }}
QPushButton:pressed {{ background: #0E1214; }}
QPushButton:disabled {{ color: #5E666A; border-color: #292F32; background: #151A1C; }}
QPushButton:focus {{ border-color: {colors.accent}; }}
QPushButton[primary="true"] {{
    color: {colors.accent_text};
    background: {colors.accent};
    border-color: {colors.accent};
    font-weight: 700;
}}
QPushButton[primary="true"]:hover {{ background: {colors.accent_hover}; }}
QPushButton[danger="true"] {{ color: {colors.danger}; border-color: {colors.danger}; }}
QPushButton[nav="true"] {{
    min-height: 34px;
    padding: 0 14px;
    background: {colors.surface_alt};
    font-weight: 600;
}}
QPushButton[nav="true"]:checked {{
    color: {colors.accent_text};
    background: {colors.accent};
    border-color: {colors.accent};
}}
QPushButton[localNav="true"] {{
    min-width: 112px;
    border-radius: 0;
    border-color: transparent;
    background: transparent;
}}
QPushButton[localNav="true"]:checked {{
    color: {colors.accent_text};
    background: {colors.accent};
    font-weight: 700;
}}
QPushButton[actionNav="true"] {{
    text-align: left;
    border: 0;
    border-radius: 3px;
    background: transparent;
}}
QPushButton[actionNav="true"]:checked {{
    color: {colors.accent_text};
    background: {colors.accent};
    font-weight: 700;
}}
QLineEdit, QComboBox, QSpinBox, QDateTimeEdit, QTextEdit {{
    min-height: 27px;
    padding: 0 8px;
    background: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 4px;
    selection-background-color: {colors.info};
}}
QTextEdit {{ padding: 6px; }}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QCheckBox {{ spacing: 5px; background: transparent; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid #667075; border-radius: 2px; }}
QCheckBox::indicator:checked {{ background: {colors.accent}; border-color: {colors.accent}; }}
QTableView, QListView {{
    background: {colors.surface};
    alternate-background-color: #151B1E;
    border: 1px solid {colors.border};
    border-radius: 4px;
    gridline-color: {colors.border};
    selection-background-color: {colors.selection};
    selection-color: {colors.text};
    outline: 0;
}}
QTableView::item {{ border-bottom: 1px solid #252C2F; padding: 2px 5px; }}
QTableView::item:selected, QListView::item:selected {{ border: 1px solid {colors.accent}; }}
QListView::item {{ padding: 7px 6px; border-bottom: 1px solid #293034; }}
QHeaderView::section {{
    min-height: 27px;
    padding: 0 6px;
    background: #171D20;
    border: 0;
    border-right: 1px solid {colors.border};
    border-bottom: 1px solid {colors.border};
    color: #C7CCCE;
    font-weight: 650;
}}
QLabel[chip="true"] {{
    padding: 2px 7px;
    border: 1px solid {colors.border};
    border-radius: 8px;
    font-weight: 600;
}}
QLabel[state="success"] {{ color: {colors.success}; border-color: #24623F; background: #153523; }}
QLabel[state="warning"] {{ color: {colors.warning}; border-color: #675326; background: #342A16; }}
QLabel[state="error"] {{ color: {colors.danger}; border-color: #6A3034; background: #361C1F; }}
QLabel[state="active"] {{ color: #70A6FF; border-color: #315995; background: #172E51; }}
QLabel[state="neutral"] {{ color: {colors.muted_text}; }}
QFrame[metric="true"] {{
    background: #111719;
    border: 1px solid {colors.border};
    border-radius: 5px;
}}
QFrame#accountActions {{ border: 1px solid {colors.accent}; background: #101517; }}
QFrame#deviceRail {{ border-color: #5A4E1B; }}
QWidget#statusBarContent {{ background: #101416; border-top: 1px solid {colors.border}; }}
QLabel[footerValue="true"] {{ color: {colors.accent}; font-weight: 750; }}
QTabWidget::pane {{ border: 1px solid {colors.border}; top: -1px; }}
QTabBar::tab {{
    padding: 7px 14px;
    background: {colors.surface_alt};
    border: 1px solid {colors.border};
}}
QTabBar::tab:selected {{ color: {colors.accent_text}; background: {colors.accent}; }}
QSplitter::handle {{ background: {colors.window}; width: 4px; height: 4px; }}
QMenu, QToolTip {{
    background: {colors.surface};
    color: {colors.text};
    border: 1px solid {colors.border};
}}
QScrollBar:vertical {{ width: 9px; background: transparent; }}
QScrollBar::handle:vertical {{ background: #485156; border-radius: 4px; min-height: 22px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
