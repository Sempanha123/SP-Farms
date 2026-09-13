from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from sp_farms.app.navigation import NavigationService


class ShortcutHelpDialog(QDialog):
    def __init__(self, navigation: NavigationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        commands = tuple(command for command in navigation.commands if command.shortcut)
        table = QTableWidget(len(commands), 2)
        table.setHorizontalHeaderLabels(("Command", "Shortcut"))
        table.verticalHeader().hide()
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, command in enumerate(commands):
            table.setItem(row, 0, QTableWidgetItem(command.title))
            table.setItem(row, 1, QTableWidgetItem(command.shortcut))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table)
