from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    CompactTable,
    EmptyState,
    MetricRow,
    Panel,
    PrimaryButton,
    StatusChip,
)


class DeviceRail(Panel):
    def __init__(
        self,
        model: QAbstractItemModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("deviceRail")
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        heading = QLabel("Device Manager")
        heading.setStyleSheet("font-weight: 650; font-size: 14px;")
        refresh = QPushButton("Refresh")
        header = QHBoxLayout()
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(refresh)
        layout.addLayout(header)
        search = QLineEdit()
        search.setPlaceholderText("Search devices")
        layout.addWidget(search)
        layout.addWidget(StatusChip("Connected fleet", "neutral"))
        self.list_view = QListView()
        self.list_view.setObjectName("deviceRailList")
        self.list_view.setUniformItemSizes(True)
        if model is not None:
            self.list_view.setModel(model)
        layout.addWidget(self.list_view, stretch=1)


class ManagementWorkspace(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("managementWorkspace")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(MetricRow((("Accounts", "0"), ("Active", "0"), ("Needs attention", "0"))))

        toolbar = Panel()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 7, 10, 7)
        toolbar_layout.addWidget(QLineEdit("Search accounts, pages, or groups"), stretch=1)
        toolbar_layout.addWidget(QPushButton("Filter"))
        toolbar_layout.addWidget(PrimaryButton("Add account"))
        layout.addWidget(toolbar)

        table = CompactTable()
        table.setObjectName("managementTable")
        model = QStandardItemModel(0, 6, table)
        model.setHorizontalHeaderLabels(
            ("Account", "Status", "Device", "Network", "Last active", "Actions")
        )
        table.setModel(model)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table, stretch=1)


class JobQueueDrawer(Panel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jobQueueDrawer")
        self.setMinimumWidth(250)
        self.setMaximumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        heading = QLabel("Job Queue")
        heading.setStyleSheet("font-weight: 650;")
        layout.addWidget(heading)
        layout.addWidget(StatusChip("0 running", "neutral"))
        layout.addWidget(EmptyState("Queue is clear", "New automation jobs will appear here."))
        layout.addStretch()


class WorkspaceLayout(QWidget):
    def __init__(
        self,
        device_model: QAbstractItemModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(7)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("workspaceSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(DeviceRail(device_model))
        splitter.addWidget(ManagementWorkspace())
        self.job_queue = JobQueueDrawer()
        splitter.addWidget(self.job_queue)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 900, 280])
        root.addWidget(splitter, stretch=1)

        status = QWidget()
        status.setObjectName("statusBarContent")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(4, 0, 4, 0)
        status_layout.setSpacing(12)
        for label in ("Devices 0", "Queued 0", "Failed 0", "Completed 0"):
            status_layout.addWidget(QLabel(label))
        status_layout.addStretch()
        status_layout.addWidget(QLabel("Ready"))
        root.addWidget(status)
