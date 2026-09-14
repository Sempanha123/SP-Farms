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
    selection: str


LIGHT_PALETTE = ThemePalette(
    window="#F4F6F3",
    surface="#FFFFFF",
    surface_alt="#EEF2ED",
    border="#D9DFD8",
    text="#20251F",
    muted_text="#667066",
    accent="#A7D95B",
    accent_hover="#96C94D",
    accent_text="#17200F",
    warning="#E7B85D",
    danger="#D9534F",
    success="#55A46B",
    selection="#E4F2CE",
)

DARK_PALETTE = ThemePalette(
    window="#171A18",
    surface="#202421",
    surface_alt="#282D29",
    border="#3A403B",
    text="#EFF3EF",
    muted_text="#A3ADA4",
    accent="#C8E66B",
    accent_hover="#D4ED83",
    accent_text="#17200F",
    warning="#E7B85D",
    danger="#E36A66",
    success="#70C184",
    selection="#35432B",
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
    font-size: 13px;
}}
QFrame[panel="true"], QDialog {{
    background: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 10px;
}}
QLabel[muted="true"] {{ color: {colors.muted_text}; }}
QPushButton {{
    min-height: 30px;
    padding: 0 12px;
    border: 1px solid {colors.border};
    border-radius: 8px;
    background: {colors.surface};
}}
QPushButton:hover {{ background: {colors.surface_alt}; }}
QPushButton:focus {{ border: 2px solid {colors.accent}; }}
QPushButton[primary="true"] {{
    color: {colors.accent_text};
    background: {colors.accent};
    border-color: {colors.accent};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{ background: {colors.accent_hover}; }}
QPushButton[danger="true"] {{ color: {colors.danger}; border-color: {colors.danger}; }}
QLineEdit, QComboBox, QSpinBox, QDateTimeEdit, QTextEdit {{
    min-height: 30px;
    padding: 0 8px;
    background: {colors.surface};
    border: 1px solid {colors.border};
    border-radius: 8px;
    selection-background-color: {colors.selection};
}}
QTableView {{
    background: {colors.surface};
    alternate-background-color: {colors.surface_alt};
    border: 1px solid {colors.border};
    border-radius: 8px;
    gridline-color: {colors.border};
    selection-background-color: {colors.selection};
    selection-color: {colors.text};
}}
QHeaderView::section {{
    min-height: 28px;
    padding: 0 8px;
    background: {colors.surface_alt};
    border: 0;
    border-bottom: 1px solid {colors.border};
    color: {colors.muted_text};
    font-weight: 600;
}}
QMenu, QToolTip {{
    background: {colors.surface};
    color: {colors.text};
    border: 1px solid {colors.border};
}}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {colors.border}; border-radius: 5px; min-height: 24px; }}
"""
