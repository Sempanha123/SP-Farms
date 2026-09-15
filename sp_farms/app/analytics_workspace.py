"""Analytics and live engagement monitoring workspace UI with social and device reliability tabs."""

import logging
from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSplitter,
    QTabWidget,
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
from sp_farms.application.device_analytics_service import DeviceAnalyticsService
from sp_farms.domain.analytics import PostAnalyticsSnapshot
from sp_farms.domain.device_analytics import (
    DeviceReliabilityStats,
)

logger = logging.getLogger(__name__)


class AnalyticsTableModel(QAbstractTableModel):
    HEADERS = [
        "Synced At",
        "External ID",
        "Destination",
        "Type",
        "Likes",
        "Comments",
        "Shares",
        "Reach",
        "Eng. %",
    ]

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
    ) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        row = index.row()
        col = index.column()
        if row >= len(self._snapshots):
            return None

        snap = self._snapshots[row]
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


class DeviceReliabilityTableModel(QAbstractTableModel):
    HEADERS = [
        "Device Key",
        "Provider",
        "Reliability",
        "Rating",
        "Uptime %",
        "Disconnects",
        "Jobs (S/F/R)",
        "Avg Duration",
        "Error Rate",
    ]

    def __init__(self, stats: Sequence[DeviceReliabilityStats] = ()) -> None:
        super().__init__()
        self._stats: list[DeviceReliabilityStats] = list(stats)

    def set_stats(self, stats: Sequence[DeviceReliabilityStats]) -> None:
        self.beginResetModel()
        self._stats = list(stats)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self._stats)

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
    ) -> Any:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        row = index.row()
        col = index.column()
        if row >= len(self._stats):
            return None

        s = self._stats[row]
        if col == 0:
            return s.device_key
        elif col == 1:
            return s.provider.upper()
        elif col == 2:
            return f"{s.reliability_score:.1f}%"
        elif col == 3:
            return s.rating.value.upper()
        elif col == 4:
            return f"{s.uptime_percentage:.1f}%"
        elif col == 5:
            return str(s.disconnect_count)
        elif col == 6:
            return f"{s.successful_jobs}/{s.failed_jobs}/{s.retried_jobs}"
        elif col == 7:
            return f"{s.average_job_duration_seconds:.1f}s"
        elif col == 8:
            return f"{s.provider_error_rate:.1f}%"
        return None

    def get_stat(self, row: int) -> DeviceReliabilityStats | None:
        if 0 <= row < len(self._stats):
            return self._stats[row]
        return None


class AnalyticsWorkspace(QWidget):
    """Real-time analytics and reliability monitoring dashboard."""

    def __init__(self, analytics_service_or_context: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if hasattr(analytics_service_or_context, "analytics_service"):
            self.social_service: AnalyticsService | None = getattr(
                analytics_service_or_context, "analytics_service", None
            )
            self.device_service: DeviceAnalyticsService | None = getattr(
                analytics_service_or_context, "device_analytics_service", None
            )
        else:
            self.social_service = analytics_service_or_context
            self.device_service = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Tab widget for Social Posts and Device Reliability
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Social Post Performance
        self.social_tab = QWidget()
        self._build_social_tab()
        self.tabs.addTab(self.social_tab, "Social Post Performance")

        # Tab 2: Device Reliability Analytics
        self.device_tab = QWidget()
        self._build_device_tab()
        self.tabs.addTab(self.device_tab, "Device & Provider Reliability")

        self.reload_data()

    def refresh(self) -> None:
        """Alias for reload_data."""
        self.reload_data()

    def reload_data(self) -> None:
        """Reload all metrics."""
        self.reload_social_data()
        self.reload_device_data()

    def _build_social_tab(self) -> None:
        layout = QVBoxLayout(self.social_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Header with Metrics Row
        self.social_metrics_row = MetricRow()
        layout.addWidget(self.social_metrics_row)

        # Toolbar
        toolbar = QHBoxLayout()
        title_lbl = QLabel("Engagement Performance & Insights")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ECEFF4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.btn_refresh_social = PrimaryButton("🔄 Refresh Insights")
        self.btn_refresh_social.clicked.connect(self.reload_social_data)
        toolbar.addWidget(self.btn_refresh_social)
        layout.addLayout(toolbar)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Table
        left_panel = Panel()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        self.table_model = AnalyticsTableModel()
        self.table_view = CompactTable()
        self.table_view.setModel(self.table_model)
        self.table_view.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table_view.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_view.selectionModel().selectionChanged.connect(self._on_social_row_selected)
        left_layout.addWidget(self.table_view)

        splitter.addWidget(left_panel)

        # Right Inspector Panel
        self.inspector_panel = Panel()
        insp_layout = QVBoxLayout(self.inspector_panel)
        insp_layout.setContentsMargins(12, 12, 12, 12)
        insp_layout.setSpacing(8)

        self.lbl_insp_title = QLabel("Select a post to inspect details")
        self.lbl_insp_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #88C0D0;")
        self.lbl_insp_title.setWordWrap(True)
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

    def _build_device_tab(self) -> None:
        layout = QVBoxLayout(self.device_tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.device_metrics_row = MetricRow()
        layout.addWidget(self.device_metrics_row)

        toolbar = QHBoxLayout()
        title_lbl = QLabel("Device Fleet & Provider Reliability")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #ECEFF4;")
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()

        self.btn_export_csv = SecondaryButton("📥 Export CSV")
        self.btn_export_csv.clicked.connect(self._export_device_csv)
        toolbar.addWidget(self.btn_export_csv)

        self.btn_export_json = SecondaryButton("📄 Export JSON")
        self.btn_export_json.clicked.connect(self._export_device_json)
        toolbar.addWidget(self.btn_export_json)

        self.btn_refresh_devices = PrimaryButton("🔄 Refresh Fleet")
        self.btn_refresh_devices.clicked.connect(self.reload_device_data)
        toolbar.addWidget(self.btn_refresh_devices)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = Panel()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        self.device_table_model = DeviceReliabilityTableModel()
        self.device_table_view = CompactTable()
        self.device_table_view.setModel(self.device_table_model)
        hh = self.device_table_view.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.device_table_view.selectionModel().selectionChanged.connect(
            self._on_device_row_selected
        )
        left_layout.addWidget(self.device_table_view)

        splitter.addWidget(left_panel)

        self.device_inspector_panel = Panel()
        insp_layout = QVBoxLayout(self.device_inspector_panel)
        insp_layout.setContentsMargins(12, 12, 12, 12)
        insp_layout.setSpacing(8)

        self.lbl_device_insp_title = QLabel("Select a device to view diagnostics")
        self.lbl_device_insp_title.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #A3BE8C;"
        )
        self.lbl_device_insp_title.setWordWrap(True)
        insp_layout.addWidget(self.lbl_device_insp_title)

        self.lbl_device_insp_details = QLabel()
        self.lbl_device_insp_details.setWordWrap(True)
        self.lbl_device_insp_details.setStyleSheet("color: #D8DEE9; line-height: 1.4;")
        insp_layout.addWidget(self.lbl_device_insp_details)
        insp_layout.addStretch()

        splitter.addWidget(self.device_inspector_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def reload_social_data(self) -> None:
        """Fetch latest snapshots and aggregate metrics for social posts."""
        if not self.social_service:
            return
        snaps = self.social_service.list_recent_snapshots(limit=100)
        self.table_model.set_snapshots(snaps)

        summary = self.social_service.get_summary()
        self.social_metrics_row.set_metrics(
            [
                ("Total Tracked Posts", f"{summary.total_posts:,}"),
                ("Total Reach", f"{summary.total_reach:,}"),
                ("Total Interactions", f"{summary.total_interactions:,}"),
                ("Avg Engagement", f"{summary.average_engagement_rate:.1f}%"),
            ]
        )

    def reload_device_data(self) -> None:
        """Fetch latest device reliability statistics."""
        if not self.device_service:
            return
        report = self.device_service.generate_fleet_report()
        self.device_table_model.set_stats(report.device_stats)

        total_devices = len(report.device_stats)
        unreliable_count = len(report.unreliable_devices)
        self.device_metrics_row.set_metrics(
            [
                ("Monitored Devices", str(total_devices)),
                ("Fleet Health Score", f"{report.overall_score:.1f}%"),
                ("Unreliable Devices", str(unreliable_count)),
                ("Active Providers", str(len(report.provider_stats))),
            ]
        )

    def _export_device_csv(self) -> None:
        if not self.device_service:
            return
        csv_data = self.device_service.export_diagnostics_csv()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Fleet Diagnostics CSV",
            "device_reliability.csv",
            "CSV Files (*.csv)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(csv_data)

    def _export_device_json(self) -> None:
        if not self.device_service:
            return
        json_data = self.device_service.export_diagnostics_json()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Fleet Diagnostics JSON",
            "device_reliability.json",
            "JSON Files (*.json)",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_data)

    def _on_social_row_selected(self) -> None:
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
            f"<b>Total Interactions:</b> {snap.total_interactions:,}<br>"
            f"<b>Engagement Rate:</b> {snap.engagement_rate:.2f}%<br>"
            f"<b>Last Synced:</b> {snap.synced_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )
        self.lbl_insp_details.setText(details)

    def _on_device_row_selected(self) -> None:
        indexes = self.device_table_view.selectionModel().selectedRows()
        if not indexes:
            self.lbl_device_insp_title.setText("Select a device to view diagnostics")
            self.lbl_device_insp_details.setText("")
            return

        row = indexes[0].row()
        stat = self.device_table_model.get_stat(row)
        if not stat:
            return

        self.lbl_device_insp_title.setText(f"Device: {stat.device_key}")
        last_seen_str = (
            stat.last_seen.strftime("%Y-%m-%d %H:%M:%S UTC") if stat.last_seen else "Never"
        )
        rating_str = stat.rating.value.upper()
        details = (
            f"<b>Provider:</b> {stat.provider.upper()}<br>"
            f"<b>Serial:</b> {stat.serial}<br>"
            f"<b>Reliability Score:</b> {stat.reliability_score:.1f}% ({rating_str})<br>"
            f"<b>Uptime Percentage:</b> {stat.uptime_percentage:.1f}%<br>"
            f"<b>Disconnect Count:</b> {stat.disconnect_count}<br>"
            f"<b>Total Jobs Executed:</b> {stat.total_jobs}<br>"
            f"<b>Successful Jobs:</b> {stat.successful_jobs}<br>"
            f"<b>Failed Jobs:</b> {stat.failed_jobs}<br>"
            f"<b>Retried Jobs:</b> {stat.retried_jobs}<br>"
            f"<b>Job Success Rate:</b> {stat.job_success_rate:.1f}%<br>"
            f"<b>Average Duration:</b> {stat.average_job_duration_seconds:.2f}s<br>"
            f"<b>Provider Error Rate:</b> {stat.provider_error_rate:.1f}%<br>"
            f"<b>Last Seen:</b> {last_seen_str}"
        )
        self.lbl_device_insp_details.setText(details)
