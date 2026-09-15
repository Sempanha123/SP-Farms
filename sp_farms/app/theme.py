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
    window="#F4F5F2",
    surface="#FFFFFF",
    surface_alt="#ECEFEC",
    border="#CCD1CC",
    text="#171C19",
    muted_text="#667069",
    accent="#F4C915",
    accent_hover="#FFD92D",
    accent_text="#16170F",
    warning="#D99B18",
    danger="#D84D53",
    success="#22B967",
    info="#2D76DF",
    selection="#FFF3A9",
)

DARK_PALETTE = ThemePalette(
    window="#0D1113",
    surface="#121719",
    surface_alt="#181E21",
    border="#333D41",
    text="#F2F4F4",
    muted_text="#98A2A7",
    accent="#F4C915",
    accent_hover="#FFD92D",
    accent_text="#15160E",
    warning="#E3A629",
    danger="#F05D63",
    success="#25D06F",
    info="#4388F0",
    selection="#37361D",
)


def palette(mode: ThemeMode) -> ThemePalette:
    return LIGHT_PALETTE if mode is ThemeMode.LIGHT else DARK_PALETTE


def style_sheet(mode: ThemeMode) -> str:
    c = palette(mode)
    dark = mode is ThemeMode.DARK

    top = "#101518" if dark else "#FAFBF9"
    raised = "#161C1F" if dark else "#FFFFFF"
    soft = "#151A1D" if dark else "#F5F7F5"
    hover = "#20272A" if dark else "#E8ECE9"
    row_line = "#252D30" if dark else "#DDE2DE"
    header = "#171E21" if dark else "#E9EEEA"
    success_bg = "#153523" if dark else "#E6F7ED"
    warning_bg = "#342A16" if dark else "#FFF4D9"
    error_bg = "#361C20" if dark else "#FDECEE"
    active_bg = "#172D4E" if dark else "#EBF2FF"
    yellow_soft = "#2C2913" if dark else "#FFF8D2"
    flow_done = "#183B27" if dark else "#E4F7EB"
    flow_next = "#2E2A13" if dark else "#FFF5C8"

    return f"""
QWidget {{
    background: {c.window};
    color: {c.text};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 12px;
}}

QFrame[panel="true"], QDialog {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 8px;
}}

QFrame[softPanel="true"] {{
    background: {soft};
    border: 1px solid {c.border};
    border-radius: 8px;
}}

QFrame[flowPanel="true"] {{
    background: {raised};
    border: 1px solid #61551D;
    border-radius: 8px;
}}

QFrame[metric="true"] {{
    min-height: 58px;
    background: {raised};
    border: 1px solid {c.border};
    border-radius: 8px;
}}

QLabel {{
    background: transparent;
    border: 0;
}}

QLabel[muted="true"] {{
    color: {c.muted_text};
}}

QLabel[heading="true"] {{
    font-size: 16px;
    font-weight: 700;
}}

QLabel[sectionTitle="true"] {{
    font-size: 13px;
    font-weight: 700;
}}

QLabel[metricValue="true"] {{
    font-size: 19px;
    font-weight: 750;
}}

QLabel[flowArrow="true"] {{
    color: {c.muted_text};
    font-size: 16px;
    font-weight: 700;
}}

QLabel#brand {{
    font-size: 20px;
    font-weight: 800;
}}

QLabel#brandVersion, QLabel#brandSubtitle {{
    color: {c.muted_text};
}}

QLabel#brandSubtitle {{
    font-size: 10px;
}}

QWidget#topNavigation {{
    background: {top};
    border-bottom: 1px solid {c.border};
}}

QLabel#brandMark {{
    color: #07130C;
    background: #3ECF72;
    border: 1px solid #57DF88;
    border-radius: 9px;
    font-size: 19px;
    font-weight: 900;
}}

QPushButton {{
    min-height: 29px;
    padding: 0 10px;
    border: 1px solid {c.border};
    border-radius: 7px;
    background: {c.surface_alt};
}}

QPushButton:hover {{
    background: {hover};
    border-color: #59656A;
}}

QPushButton:focus {{
    border: 2px solid {c.accent};
    outline: none;
}}

QPushButton[primary="true"] {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QPushButton[primary="true"]:hover {{
    background: {c.accent_hover};
    border-color: {c.accent_hover};
}}

QPushButton[successAction="true"] {{
    color: #07160D;
    background: {c.success};
    border-color: {c.success};
    font-weight: 700;
}}

QPushButton[infoAction="true"] {{
    color: white;
    background: {c.info};
    border-color: {c.info};
    font-weight: 700;
}}

QPushButton[nav="true"] {{
    min-height: 34px;
    padding: 0 13px;
    background: {c.surface_alt};
    font-weight: 600;
}}

QPushButton[nav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QPushButton[localNav="true"] {{
    min-width: 102px;
    background: transparent;
    border-color: transparent;
}}

QPushButton[localNav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QPushButton[actionNav="true"] {{
    text-align: left;
    background: transparent;
    border-color: transparent;
}}

QPushButton[actionNav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    font-weight: 700;
}}

QPushButton[flowStep="true"] {{
    min-height: 46px;
    min-width: 125px;
    padding: 4px 10px;
    text-align: left;
    background: {soft};
    border-color: {c.border};
    border-radius: 8px;
    font-weight: 650;
}}

QPushButton[flowStep="true"]:hover {{
    background: {yellow_soft};
    border-color: {c.accent};
}}

QPushButton[flowState="done"] {{
    color: {c.success};
    background: {flow_done};
    border-color: #2B7047;
}}

QPushButton[flowState="next"] {{
    color: {c.accent};
    background: {flow_next};
    border-color: #6A5D1C;
}}

QPushButton[quickAction="true"] {{
    min-height: 48px;
    text-align: left;
    padding: 6px 10px;
    background: {raised};
    border-radius: 8px;
}}

QPushButton[quickAction="true"]:hover {{
    background: {hover};
    border-color: {c.accent};
}}

QLineEdit, QComboBox, QSpinBox, QDateTimeEdit, QTextEdit {{
    min-height: 29px;
    padding: 0 8px;
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 7px;
    selection-background-color: {c.info};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateTimeEdit:focus, QTextEdit:focus {{
    border: 2px solid {c.accent};
}}

QTextEdit {{
    padding: 6px;
}}

QCheckBox {{
    spacing: 5px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #667177;
    border-radius: 3px;
}}

QCheckBox::indicator:checked {{
    background: {c.accent};
    border-color: {c.accent};
}}

QGroupBox {{
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    background: {soft};
    border: 1px solid {c.border};
    border-radius: 8px;
    font-weight: 650;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 5px;
    background: {c.window};
}}

QTableView, QListView, QListWidget, QTreeView {{
    background: {c.surface};
    alternate-background-color: {soft};
    border: 1px solid {c.border};
    border-radius: 7px;
    gridline-color: {c.border};
    selection-background-color: {c.selection};
    selection-color: {c.text};
    outline: 0;
}}

QTableView::item {{
    padding: 2px 5px;
    border-bottom: 1px solid {row_line};
}}

QTableView::item:selected, QListView::item:selected {{
    border-left: 2px solid {c.accent};
}}

QListView::item, QListWidget::item {{
    padding: 6px;
    border-bottom: 1px solid {row_line};
}}

QHeaderView::section {{
    min-height: 28px;
    padding: 0 6px;
    background: {header};
    border: 0;
    border-right: 1px solid {c.border};
    border-bottom: 1px solid {c.border};
    font-weight: 650;
}}

QLabel[chip="true"] {{
    padding: 2px 7px;
    border: 1px solid {c.border};
    border-radius: 8px;
    font-weight: 600;
}}

QLabel[state="success"] {{
    color: {c.success};
    background: {success_bg};
    border-color: #28633F;
}}

QLabel[state="warning"] {{
    color: {c.warning};
    background: {warning_bg};
    border-color: #695527;
}}

QLabel[state="error"] {{
    color: {c.danger};
    background: {error_bg};
    border-color: #70343A;
}}

QLabel[state="active"] {{
    color: #78A8FF;
    background: {active_bg};
    border-color: #315A95;
}}

QLabel[state="neutral"] {{
    color: {c.muted_text};
}}

QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: 7px;
}}

QTabBar::tab {{
    min-height: 29px;
    padding: 0 12px;
    margin-right: 2px;
    background: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 6px;
}}

QTabBar::tab:hover {{
    background: {hover};
}}

QTabBar::tab:selected {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QTabWidget#contextTabs QTabBar::tab {{
    min-width: 145px;
    min-height: 30px;
    margin: 1px 4px 1px 0;
    text-align: left;
}}

QProgressBar {{
    min-height: 12px;
    background: {soft};
    border: 1px solid {c.border};
    border-radius: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {c.success};
    border-radius: 5px;
}}

QScrollArea {{
    border: 0;
    background: transparent;
}}

QSplitter::handle {{
    background: {c.window};
    width: 4px;
    height: 4px;
}}

QSplitter::handle:hover {{
    background: {c.accent};
}}

QMenu, QToolTip {{
    background: {c.surface};
    color: {c.text};
    border: 1px solid {c.border};
}}

QMenu::item {{
    padding: 6px 22px 6px 10px;
}}

QMenu::item:selected {{
    background: {c.selection};
}}

QScrollBar:vertical {{
    width: 9px;
    background: transparent;
}}

QScrollBar::handle:vertical {{
    background: #485156;
    border-radius: 4px;
    min-height: 22px;
}}

QScrollBar:horizontal {{
    height: 9px;
    background: transparent;
}}

QScrollBar::handle:horizontal {{
    background: #485156;
    border-radius: 4px;
    min-width: 22px;
}}
"""
