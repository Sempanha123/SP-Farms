from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

_ROOT_INDEX = QModelIndex()


class NotificationLevel(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Notification:
    id: str
    message: str
    level: NotificationLevel
    created_at: datetime


class NotificationCenterModel(QAbstractListModel):
    MessageRole = Qt.ItemDataRole.UserRole + 1
    LevelRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self) -> None:
        super().__init__()
        self._items: list[Notification] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        item = self._items[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, self.MessageRole):
            return item.message
        if role == self.LevelRole:
            return item.level.value
        return None

    def enqueue(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
    ) -> Notification:
        item = Notification(str(uuid4()), message, level, datetime.now(UTC))
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()
        return item

    def dismiss(self, notification_id: str) -> bool:
        row = next((i for i, item in enumerate(self._items) if item.id == notification_id), None)
        if row is None:
            return False
        self.beginRemoveRows(QModelIndex(), row, row)
        self._items.pop(row)
        self.endRemoveRows()
        return True


class Toast(QFrame):
    def __init__(
        self,
        notification: Notification,
        parent: QWidget | None = None,
        timeout_ms: int = 4000,
    ) -> None:
        super().__init__(parent)
        self.setProperty("panel", True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 7, 7)
        layout.addWidget(QLabel(notification.message), stretch=1)
        dismiss = QPushButton("Dismiss")
        dismiss.clicked.connect(self.close)
        layout.addWidget(dismiss)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, self.close)


class ProgressOverlay(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("progressOverlay")
        self.setProperty("panel", True)
        layout = QVBoxLayout(self)
        self.message = QLabel("Working…")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.message)
        layout.addStretch()
        self.hide()

    def start(self, message: str) -> None:
        self.message.setText(message)
        self.show()
        self.raise_()

    def finish(self) -> None:
        self.hide()
