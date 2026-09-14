"""Analytics and live engagement monitoring workspace UI."""

import logging
from collections.abc import Sequence

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    CompactTable,
    MetricRow,
    Panel,
    PrimaryButton,
    SecondaryButton,
)
from sp_farms.application.analytics_service import AnalyticsService
from sp_farms.domain.analytics import AggregatedMetrics, PostAnalyticsSnapshot

logger = logging.getLogger(__name__)


class AnalyticsTableModel(QAbstractTableModel):
    HEADERS = ["Synced At", "External ID", "Destination", "Type", "Likes", "Comments", "Shares", "Reach", "Eng. %"]

    def __init__(self, snapshots: Sequence[PostAnalyticsSnapshot] = ()) -> None:
        super().__init__()
        self._snapshots: list[PostAnalyticsSnapshot] = list(snapshots)

    def set_snapshots(self, snapshots: Sequence[PostAnalyticsSnapshot]) -> None:
        self.beginResetModel()
        self._snapshots = list(snapshots)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self._snapshots)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self.HEADERS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> str | None:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        snap = self._snapshots[index.row()]
        col = index.column()

        if col == 0:
            return snap.synced_at.strftime("%Y-%m-%d %H:%M")
        elif col == 1:
            return snap.external_post_id
        elif col == 2:
            return snap.destination_name
        elif col == 3:
            return snap.post_type.value.upper()
        elif col == 4:
            return f"{snap.likes_count:,}"
        elif col == 5:
            return f"{snap.comments_count:,}"
        elif col == 6:
            return f"{snap.shares_count:,}"
        elif col == 7:
            return f"{snap.reach_count:,}"
        elif col == 8:
            return f"{snap.engagement_rate:.1f}%"
        return None

    def get_snapshot(self, row: int) -> PostAnalyticsSnapshot | None:
        if 0 <= row < len(self._snapshots):
            return self._snapshots[row]
        return None


class AnalyticsWorkspace(QWidget):
    """Real-time analytics and social post engagement monitoring dashboard."""

    def __init__(self, analytics_service: AnalyticsService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = analytics_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with Metrics Row
        self.metrics_row = MetricRow()
        layout.addWidget(self.metrics_row)

        # Toolbar
        toolbar = QHBoxLayout()
        self.title_lbl = QLabel("Engagement Performance & Insights")
        self.title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ECEFF4;")
        toolbar.addWidget(self.title_lbl)
        toolbar.addStretch()

        self.btn_refresh = PrimaryButton("🔄 Refresh Insights")
        self.btn_refresh.clicked.connect(self.reload_data)
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Table
        left_panel = Panel("Tracked Posts & Insights", "Real-time engagement breakdown")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        self.table_model = AnalyticsTableModel()
        self.table_view = CompactTable()
        self.table_view.setModel(self.table_model)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_view.selectionModel().selectionChanged.connect(self._on_row_selected)
        left_layout.addWidget(self.table_view)
        splitter.addWidget(left_panel)

        # Right Inspector Panel
        self.inspector_panel = Panel("Post Inspector", "Detailed metrics analysis")
        insp_layout = QVBoxLayout(self.inspector_panel)
        insp_layout.setContentsMargins(12, 12, 12, 12)
        insp_layout.setSpacing(8)

        self.lbl_insp_title = QLabel("Select a post to inspect details")
        self.lbl_insp_title.setStyleSheet("font-weight: bold; color: #88C0D0;")
        insp_layout.addWidget(self.lbl_insp_title)

        self.lbl_insp_details = QLabel()
        self.lbl_insp_details.setWordWrap(True)
        self.lbl_insp_details.setStyleSheet("color: #D8DEE9; line-height: 1.4;")
        insp_layout.addWidget(self.lbl_insp_details)
        insp_layout.addStretch()

        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)
        self.reload_data()

    def reload_data(self) -> None:
        """Fetch latest snapshots and aggregate metrics."""
        snaps = self.service.list_recent_snapshots(limit=100)
        self.table_model.set_snapshots(snaps)

        summary = self.service.get_summary()
        self.metrics_row.set_metrics(
            [
                ("Total Tracked Posts", f"{summary.total_posts:,}"),
                ("Total Reach", f"{summary.total_reach:,}"),
                ("Total Interactions", f"{summary.total_interactions:,}"),
                ("Avg Engagement", f"{summary.average_engagement_rate:.1f}%"),
            ]
        )

    def _on_row_selected(self) -> None:
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            self.lbl_insp_title.setText("Select a post to inspect details")
            self.lbl_insp_details.setText("")
            return

        row = indexes[0].row()
        snap = self.table_model.get_snapshot(row)
        if not snap:
            return

        self.lbl_insp_title.setText(f"Post: {snap.external_post_id}")
        details = (
            f"<b>Destination:</b> {snap.destination_name} ({snap.destination_id})<br>"
            f"<b>Post Type:</b> {snap.post_type.value.upper()}<br>"
            f"<b>Likes / Reactions:</b> {snap.likes_count:,}<br>"
            f"<b>Comments:</b> {snap.comments_count:,}<br>"
            f"<b>Shares:</b> {snap.shares_count:,}<br>"
            f"<b>Video Views:</b> {snap.views_count:,}<br>"
            f"<b>Impressions:</b> {snap.impressions_count:,}<br>"
            f"<b>Unique Reach:</b> {snap.reach_count:,}<br>"
            f"<b>Engagement Rate:</b> {snap.engagement_rate:.2f}%<br>"
            f"<b>Last Synced:</b> {snap.synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        self.lbl_insp_details.setText(details)
