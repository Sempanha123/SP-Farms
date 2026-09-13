from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.theme import ThemeMode, palette


class Panel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("primary", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class StatusChip(QLabel):
    _COLORS = {
        "success": "success",
        "warning": "warning",
        "error": "danger",
        "neutral": "muted_text",
    }

    def __init__(
        self,
        text: str,
        state: str = "neutral",
        mode: ThemeMode = ThemeMode.LIGHT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        colors = palette(mode)
        color = getattr(colors, self._COLORS.get(state, "muted_text"))
        self.setStyleSheet(
            f"color: {color}; border: 1px solid {color}; border-radius: 8px; padding: 2px 7px;"
        )


class EmptyState(Panel):
    def __init__(
        self,
        title: str,
        message: str,
        action_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(6)
        heading = QLabel(title)
        heading.setStyleSheet("font-weight: 600; font-size: 15px;")
        detail = QLabel(message)
        detail.setProperty("muted", True)
        detail.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(detail)
        if action_text:
            action = PrimaryButton(action_text)
            layout.addWidget(action, alignment=Qt.AlignmentFlag.AlignLeft)


class CompactTable(QTableView):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.verticalHeader().setDefaultSectionSize(34)
        self.verticalHeader().hide()
        self.horizontalHeader().setStretchLastSection(True)


class MetricRow(QWidget):
    def __init__(
        self,
        metrics: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for label, value in metrics:
            panel = Panel()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(12, 8, 12, 8)
            value_label = QLabel(value)
            value_label.setStyleSheet("font-size: 18px; font-weight: 650;")
            name_label = QLabel(label)
            name_label.setProperty("muted", True)
            panel_layout.addWidget(value_label)
            panel_layout.addWidget(name_label)
            layout.addWidget(panel)


def apply_icon_tint(widget: QWidget, mode: ThemeMode) -> None:
    widget.setProperty("iconTint", QColor(palette(mode).muted_text))
