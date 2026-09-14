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


class DestructiveButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("danger", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SecondaryButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class StatusChip(QLabel):
    _COLORS = {
        "success": "success",
        "warning": "warning",
        "error": "danger",
        "neutral": "muted_text",
        "active": "info",
    }
    _STATE_ICONS = {
        "success": "✓",
        "warning": "▲",
        "error": "✖",
        "danger": "✖",
        "active": "●",
        "info": "●",
        "neutral": "○",
        "paused": "⏸",
        "running": "▶",
    }

    def __init__(
        self,
        text: str,
        state: str = "neutral",
        mode: ThemeMode | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setProperty("chip", True)
        self.update_state(state=state, text=text, mode=mode)

    def update_state(
        self,
        state: str,
        text: str | None = None,
        mode: ThemeMode | None = None,
    ) -> None:
        raw_text = text if text is not None else self.text()
        icon = self._STATE_ICONS.get(state.lower(), "")
        # Avoid double-prefixing if icon already present
        display_text = raw_text
        if icon and not any(raw_text.startswith(ic) for ic in self._STATE_ICONS.values()):
            display_text = f"{icon} {raw_text}"

        self.setText(display_text)
        self.setProperty("state", state)
        self.setAccessibleName(f"Status: {raw_text}")
        self.setAccessibleDescription(f"Current status is {state} ({raw_text})")

        if mode is not None:
            colors = palette(mode)
            color = getattr(colors, self._COLORS.get(state, "muted_text"))
            self.setStyleSheet(f"color: {color}; border-color: {color};")
        self.style().unpolish(self)
        self.style().polish(self)


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
        metrics: Sequence[tuple[str, str]] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self.value_labels: list[QLabel] = []
        self.name_labels: list[QLabel] = []
        if metrics:
            self.set_metrics(metrics)

    def set_metrics(self, metrics: Sequence[tuple[str, str]]) -> None:
        if not self.value_labels or len(self.value_labels) != len(metrics):
            while self._layout.count():
                item = self._layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self.value_labels.clear()
            self.name_labels.clear()
            for label, value in metrics:
                panel = Panel()
                panel.setProperty("metric", True)
                panel_layout = QVBoxLayout(panel)
                panel_layout.setContentsMargins(12, 8, 12, 8)
                value_label = QLabel(value)
                value_label.setProperty("metricValue", True)
                self.value_labels.append(value_label)
                name_label = QLabel(label)
                name_label.setProperty("muted", True)
                self.name_labels.append(name_label)
                panel_layout.addWidget(value_label)
                panel_layout.addWidget(name_label)
                self._layout.addWidget(panel)
        else:
            for idx, (label, value) in enumerate(metrics):
                self.value_labels[idx].setText(value)
                self.name_labels[idx].setText(label)


def apply_icon_tint(widget: QWidget, mode: ThemeMode) -> None:
    widget.setProperty("iconTint", QColor(palette(mode).muted_text))
