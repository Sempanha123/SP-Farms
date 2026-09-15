import logging
from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

logger = logging.getLogger(__name__)


def apply_accessibility(
    widget: QWidget,
    name: str,
    description: str | None = None,
) -> QWidget:
    """Set accessible name and optional description for assistive technologies."""
    if name:
        widget.setAccessibleName(name)
    if description:
        widget.setAccessibleDescription(description)
    return widget


def chain_tab_order(widgets: Sequence[QWidget]) -> None:
    """Chain tab order sequentially across a list of focusable widgets."""
    valid_widgets = [w for w in widgets if w is not None and not w.isHidden()]
    for i in range(len(valid_widgets) - 1):
        QWidget.setTabOrder(valid_widgets[i], valid_widgets[i + 1])


def is_interactive_widget(widget: QWidget) -> bool:
    """Determine if a widget is interactive and requires accessible semantics."""
    return isinstance(
        widget,
        (
            QAbstractButton,
            QLineEdit,
            QComboBox,
            QSpinBox,
            QAbstractItemView,
        ),
    )


def verify_accessible_semantics(widget: QWidget) -> tuple[bool, str]:
    """Validate that an interactive widget has an accessible name."""
    if is_interactive_widget(widget):
        name = widget.accessibleName().strip()
        if not name and isinstance(widget, QAbstractButton):
            name = widget.text().strip()
        if not name:
            label = widget.objectName() or widget.__class__.__name__
            return False, f"Widget {label} missing accessible name"
    return True, "OK"


class AccessibleFocusManager:
    """Helper managing keyboard focus and accessible announcement signals."""

    @staticmethod
    def setup_dialog_keyboard_navigation(dialog: QWidget, close_on_escape: bool = True) -> None:
        """Configure Escape and Enter keys for dialog efficiency."""
        if close_on_escape:
            shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), dialog)
            if hasattr(dialog, "reject"):
                shortcut.activated.connect(dialog.reject)
            elif hasattr(dialog, "close"):
                shortcut.activated.connect(dialog.close)
