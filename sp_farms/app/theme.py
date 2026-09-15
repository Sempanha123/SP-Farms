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
    window="#F3F5F3",
    surface="#FFFFFF",
    surface_alt="#EEF1EF",
    border="#C9D0CC",
    text="#151A17",
    muted_text="#667069",
    accent="#EFC51B",
    accent_hover="#F8D444",
    accent_text="#14150E",
    warning="#C98916",
    danger="#D84D53",
    success="#1FAE61",
    info="#3976D8",
    selection="#FFF4BC",
)

DARK_PALETTE = ThemePalette(
    window="#0B0F11",
    surface="#111619",
    surface_alt="#171D20",
    border="#2C3539",
    text="#F3F5F5",
    muted_text="#929DA2",
    accent="#F4C915",
    accent_hover="#FFD83D",
    accent_text="#15150D",
    warning="#E0A329",
    danger="#EF5C62",
    success="#28C96F",
    info="#4B87EA",
    selection="#34331E",
)


def palette(mode: ThemeMode) -> ThemePalette:
    return LIGHT_PALETTE if mode is ThemeMode.LIGHT else DARK_PALETTE


def style_sheet(mode: ThemeMode) -> str:
    c = palette(mode)
    dark = mode is ThemeMode.DARK

    top = "#0E1315" if dark else "#FAFBFA"
    raised = "#141A1D" if dark else "#FFFFFF"
    soft = "#151B1E" if dark else "#F5F7F5"
    hover = "#20272A" if dark else "#E7ECE8"
    row_hover = "#1A2124" if dark else "#F1F4F1"
    row_line = "#222A2E" if dark else "#DEE3DF"
    header = "#161D20" if dark else "#E8EDE9"
    disabled = "#111517" if dark else "#ECEFEC"
    success_bg = "#153622" if dark else "#E8F7ED"
    warning_bg = "#352A16" if dark else "#FFF4D8"
    error_bg = "#381B20" if dark else "#FDECEE"
    info_bg = "#172A45" if dark else "#EAF1FF"

    return f"""
QWidget {{
    background: {c.window};
    color: {c.text};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 12px;
}}

QMainWindow {{
    background: {c.window};
}}

QFrame[panel="true"], QDialog {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 7px;
}}

QFrame[softPanel="true"] {{
    background: {soft};
    border: 1px solid {c.border};
    border-radius: 7px;
}}

QFrame[metric="true"] {{
    min-height: 54px;
    background: {raised};
    border: 1px solid {c.border};
    border-radius: 7px;
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
    font-size: 18px;
    font-weight: 750;
}}

QLabel#brand {{
    font-size: 20px;
    font-weight: 800;
}}

QLabel#brandVersion,
QLabel#brandSubtitle,
QLabel#clockDate {{
    color: {c.muted_text};
}}

QLabel#brandSubtitle,
QLabel#clockDate {{
    font-size: 10px;
}}

QLabel#clockTime {{
    font-size: 14px;
    font-weight: 750;
}}

QWidget#topNavigation {{
    background: {top};
    border-bottom: 1px solid {c.border};
}}

QLabel#brandMark {{
    color: #06110A;
    background: #34C86A;
    border: 1px solid #4ADB7F;
    border-radius: 10px;
    font-size: 20px;
    font-weight: 900;
}}

QPushButton {{
    min-height: 29px;
    padding: 0 10px;
    border: 1px solid {c.border};
    border-radius: 6px;
    background: {c.surface_alt};
}}

QPushButton:hover {{
    background: {hover};
    border-color: #59656A;
}}

QPushButton:pressed {{
    background: {c.surface};
}}

QPushButton:disabled {{
    color: #626A6E;
    background: {disabled};
    border-color: #262E31;
}}

QPushButton:focus {{
    border: 1px solid {c.accent};
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
    color: #06140B;
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

QPushButton[danger="true"] {{
    color: {c.danger};
    background: {error_bg};
    border-color: #71363C;
}}

QPushButton[nav="true"] {{
    min-height: 34px;
    padding: 0 12px;
    background: transparent;
    border-color: transparent;
    font-weight: 600;
}}

QPushButton[nav="true"]:hover {{
    background: {hover};
    border-color: {c.border};
}}

QPushButton[nav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QPushButton[localNav="true"] {{
    min-height: 28px;
    padding: 0 10px;
    background: transparent;
    border-color: transparent;
}}

QPushButton[localNav="true"]:hover {{
    background: {hover};
}}

QPushButton[localNav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QPushButton[actionNav="true"] {{
    min-height: 28px;
    text-align: left;
    background: transparent;
    border-color: transparent;
}}

QPushButton[actionNav="true"]:hover {{
    background: {hover};
}}

QPushButton[actionNav="true"]:checked {{
    color: {c.accent_text};
    background: {c.accent};
    border-color: {c.accent};
    font-weight: 700;
}}

QLineEdit,
QComboBox,
QSpinBox,
QDateTimeEdit,
QTextEdit {{
    min-height: 29px;
    padding: 0 8px;
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 6px;
    selection-background-color: {c.info};
}}

QTextEdit {{
    padding: 6px;
}}

QLineEdit:hover,
QComboBox:hover,
QSpinBox:hover,
QDateTimeEdit:hover,
QTextEdit:hover {{
    border-color: #505C61;
}}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDateTimeEdit:focus,
QTextEdit:focus {{
    border-color: {c.accent};
}}

QCheckBox {{
    spacing: 5px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid #677177;
    border-radius: 3px;
}}

QCheckBox::indicator:hover {{
    border-color: {c.accent};
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
    border-radius: 7px;
    font-weight: 650;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 5px;
    background: {c.window};
}}

QTableView,
QListView,
QListWidget,
QTreeView,
QTreeWidget {{
    background: {c.surface};
    alternate-background-color: {soft};
    border: 1px solid {c.border};
    border-radius: 6px;
    gridline-color: {c.border};
    selection-background-color: {c.selection};
    selection-color: {c.text};
    outline: 0;
}}

QTableView::item {{
    padding: 2px 5px;
    border-bottom: 1px solid {row_line};
}}

QTableView::item:hover,
QListView::item:hover,
QListWidget::item:hover,
QTreeView::item:hover {{
    background: {row_hover};
}}

QTableView::item:selected,
QListView::item:selected,
QListWidget::item:selected,
QTreeView::item:selected {{
    background: {c.selection};
    border-left: 2px solid {c.accent};
}}

QListView::item,
QListWidget::item,
QTreeView::item {{
    padding: 5px 6px;
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
    border-color: #6A5424;
}}

QLabel[state="error"] {{
    color: {c.danger};
    background: {error_bg};
    border-color: #71363C;
}}

QLabel[state="active"] {{
    color: #78A8FF;
    background: {info_bg};
    border-color: #335E96;
}}

QLabel[state="neutral"] {{
    color: {c.muted_text};
}}

QTabWidget::pane {{
    border: 1px solid {c.border};
    border-radius: 6px;
    top: -1px;
}}

QTabBar::tab {{
    min-height: 29px;
    padding: 0 12px;
    margin-right: 2px;
    background: {c.surface_alt};
    border: 1px solid {c.border};
    border-radius: 5px;
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
    min-width: 148px;
    min-height: 30px;
    margin: 1px 4px 1px 0;
    text-align: left;
}}

QProgressBar {{
    min-height: 11px;
    background: {soft};
    border: 1px solid {c.border};
    border-radius: 5px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {c.success};
    border-radius: 4px;
}}

QSplitter::handle {{
    background: {c.window};
    width: 4px;
    height: 4px;
}}

QSplitter::handle:hover {{
    background: {c.accent};
}}

QMenu,
QToolTip {{
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

QScrollArea {{
    border: 0;
    background: transparent;
}}

QScrollBar:vertical {{
    width: 9px;
    background: transparent;
}}

QScrollBar::handle:vertical {{
    background: #465156;
    border-radius: 4px;
    min-height: 22px;
}}

QScrollBar:horizontal {{
    height: 9px;
    background: transparent;
}}

QScrollBar::handle:horizontal {{
    background: #465156;
    border-radius: 4px;
    min-width: 22px;
}}
"""
