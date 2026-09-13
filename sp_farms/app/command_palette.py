from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from sp_farms.app.navigation import Command, NavigationService


class CommandPalette(QDialog):
    def __init__(self, navigation: NavigationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._navigation = navigation
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search commands and modules")
        self.results = QListWidget()
        self.results.setObjectName("commandResults")
        layout.addWidget(self.search)
        layout.addWidget(self.results)

        self.search.textChanged.connect(self._populate)
        self.search.returnPressed.connect(self.execute_current)
        self.results.itemActivated.connect(lambda _: self.execute_current())
        self._populate("")

    def open(self) -> None:
        self._populate("")
        self.search.clear()
        super().open()
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def execute_current(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        command_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._navigation.execute(command_id)
        self.accept()

    def _populate(self, query: str) -> None:
        self.results.clear()
        for command in self._navigation.search(query):
            self.results.addItem(self._item(command))
        if self.results.count():
            self.results.setCurrentRow(0)

    @staticmethod
    def _item(command: Command) -> QListWidgetItem:
        label = command.title
        if command.shortcut:
            label = f"{label}    {command.shortcut}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, command.id)
        return item
