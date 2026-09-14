from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.theme import ThemeMode, style_sheet
from sp_farms.app.widgets import EmptyState, MetricRow, Panel, PrimaryButton, StatusChip


class DesignPreview(QMainWindow):
    def __init__(self, mode: ThemeMode = ThemeMode.DARK) -> None:
        super().__init__()
        self.setWindowTitle("SP-Farms Design System")
        self.resize(900, 620)
        self.setStyleSheet(style_sheet(mode))

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        heading = QLabel("SP-Farms workspace")
        heading.setStyleSheet("font-size: 20px; font-weight: 650;")
        layout.addWidget(heading)
        layout.addWidget(MetricRow((("Accounts", "24"), ("Online", "8"), ("Queued", "3"))))

        controls = Panel()
        controls_layout = QHBoxLayout(controls)
        controls_layout.addWidget(QLineEdit("Search accounts"))
        controls_layout.addWidget(StatusChip("Online", "success", mode))
        controls_layout.addWidget(StatusChip("Needs attention", "warning", mode))
        controls_layout.addWidget(PrimaryButton("Add account"))
        layout.addWidget(controls)
        layout.addWidget(
            EmptyState(
                "No account selected",
                "Select an authorized account to open its workspace and available actions.",
                "Browse accounts",
            )
        )
        self.setCentralWidget(root)


def show_design_preview() -> int:
    application = QApplication.instance() or QApplication([])
    window = DesignPreview()
    window.show()
    return application.exec()
