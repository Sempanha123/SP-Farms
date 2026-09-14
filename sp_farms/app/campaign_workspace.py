"""Campaign Manager workspace UI for multi-destination campaign orchestration."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import CompactTable, MetricRow, PrimaryButton, SecondaryButton
from sp_farms.domain.campaigns import (
    ApprovalPolicy,
    Campaign,
    CampaignStatus,
    CampaignTarget,
    SchedulePolicy,
    SchedulePolicyType,
    TargetStatus,
)
from sp_farms.domain.composer import PostType

if TYPE_CHECKING:
    from sp_farms.application.campaign_service import CampaignService


CAMPAIGN_COLUMNS = (
    ("title", "Title"),
    ("status", "Status"),
    ("post_type", "Post Type"),
    ("targets", "Targets"),
    ("completion", "Completion"),
    ("approval", "Approval"),
    ("schedule", "Schedule"),
    ("created_at", "Created"),
)

STATUS_COLORS: dict[CampaignStatus, str] = {
    CampaignStatus.DRAFT: "#94a3b8",
    CampaignStatus.READY: "#22d3ee",
    CampaignStatus.WAITING_APPROVAL: "#f59e0b",
    CampaignStatus.SCHEDULED: "#818cf8",
    CampaignStatus.RUNNING: "#34d399",
    CampaignStatus.PAUSED: "#fbbf24",
    CampaignStatus.COMPLETED: "#22c55e",
    CampaignStatus.PARTIALLY_COMPLETED: "#fb923c",
    CampaignStatus.FAILED: "#ef4444",
    CampaignStatus.ARCHIVED: "#64748b",
}


class CampaignTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._campaigns: list[Campaign] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._campaigns)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(CAMPAIGN_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._campaigns)):
            return None
        campaign = self._campaigns[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return campaign.title
            elif col == 1:
                return campaign.status.value.replace("_", " ").title()
            elif col == 2:
                return campaign.post_type.value.title()
            elif col == 3:
                return str(len(campaign.targets))
            elif col == 4:
                summary = campaign.generate_summary()
                return f"{summary.completion_percentage}%"
            elif col == 5:
                return campaign.approval_policy.value.title()
            elif col == 6:
                return campaign.schedule_policy.policy_type.value.replace("_", " ").title()
            elif col == 7:
                return campaign.created_at.strftime("%Y-%m-%d %H:%M")
        elif role == Qt.ItemDataRole.ForegroundRole and col == 1:
            color = STATUS_COLORS.get(campaign.status, "#94a3b8")
            return QColor(color)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 2, 3, 4, 5, 6, 7):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.UserRole:
            return campaign

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(CAMPAIGN_COLUMNS)
        ):
            return CAMPAIGN_COLUMNS[section][1]
        return None

    def set_campaigns(self, campaigns: Sequence[Campaign]) -> None:
        self.beginResetModel()
        self._campaigns = list(campaigns)
        self.endResetModel()

    def get_campaign(self, row: int) -> Campaign | None:
        if 0 <= row < len(self._campaigns):
            return self._campaigns[row]
        return None


class CampaignFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search_text: str = ""
        self._status_filter: str = "All"

    def set_search(self, text: str) -> None:
        self._search_text = text.lower()
        self.invalidate()

    def set_status_filter(self, status: str) -> None:
        self._status_filter = status
        self.invalidate()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, CampaignTableModel):
            return True
        campaign = model.get_campaign(source_row)
        if campaign is None:
            return False

        if self._status_filter != "All":
            status_display = campaign.status.value.replace("_", " ").title()
            if status_display != self._status_filter:
                return False

        if self._search_text:
            searchable = (
                campaign.title.lower()
                + " "
                + campaign.caption.lower()
                + " "
                + " ".join(campaign.tags).lower()
            )
            if self._search_text not in searchable:
                return False

        return True


TARGET_COLUMNS = (
    ("destination", "Destination"),
    ("type", "Type"),
    ("status", "Status"),
    ("attempts", "Attempts"),
    ("post_id", "Post ID"),
    ("error", "Error"),
    ("executed_at", "Executed"),
)


class TargetTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._targets: list[CampaignTarget] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._targets)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(TARGET_COLUMNS)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self._targets)):
            return None
        target = self._targets[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return target.destination_name
            elif col == 1:
                return target.destination_type.value.title()
            elif col == 2:
                return target.status.value.title()
            elif col == 3:
                return str(target.attempt_count)
            elif col == 4:
                return target.published_post_id or "—"
            elif col == 5:
                return target.error_message or "—"
            elif col == 6:
                if target.executed_at:
                    return target.executed_at.strftime("%Y-%m-%d %H:%M")
                return "—"
        elif role == Qt.ItemDataRole.ForegroundRole and col == 2:
            color_map = {
                TargetStatus.PENDING: "#94a3b8",
                TargetStatus.RUNNING: "#34d399",
                TargetStatus.SUCCESS: "#22c55e",
                TargetStatus.FAILED: "#ef4444",
                TargetStatus.SKIPPED: "#64748b",
            }
            return QColor(color_map.get(target.status, "#94a3b8"))
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (1, 2, 3, 6):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.UserRole:
            return target

        return None

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(TARGET_COLUMNS)
        ):
            return TARGET_COLUMNS[section][1]
        return None

    def set_targets(self, targets: Sequence[CampaignTarget]) -> None:
        self.beginResetModel()
        self._targets = list(targets)
        self.endResetModel()


class NewCampaignDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Campaign")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Campaign title...")
        form.addRow("Title:", self.title_input)

        self.post_type_combo = QComboBox()
        self.post_type_combo.addItems(["Feed", "Reel", "Story"])
        form.addRow("Post Type:", self.post_type_combo)

        self.caption_input = QPlainTextEdit()
        self.caption_input.setPlaceholderText("Campaign caption text...")
        self.caption_input.setMaximumHeight(100)
        form.addRow("Caption:", self.caption_input)

        self.approval_combo = QComboBox()
        self.approval_combo.addItems(["Manual", "Automatic"])
        form.addRow("Approval:", self.approval_combo)

        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems(["Immediate", "Scheduled Once", "Staggered"])
        form.addRow("Schedule:", self.schedule_combo)

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Campaign notes...")
        self.notes_input.setMaximumHeight(60)
        form.addRow("Notes:", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_campaign_data(self) -> dict[str, object]:
        post_type_map = {"Feed": PostType.FEED, "Reel": PostType.REEL, "Story": PostType.STORY}
        approval_map = {"Manual": ApprovalPolicy.MANUAL, "Automatic": ApprovalPolicy.AUTOMATIC}
        schedule_map = {
            "Immediate": SchedulePolicyType.IMMEDIATE,
            "Scheduled Once": SchedulePolicyType.SCHEDULED_ONCE,
            "Staggered": SchedulePolicyType.STAGGERED,
        }
        return {
            "title": self.title_input.text().strip(),
            "post_type": post_type_map.get(self.post_type_combo.currentText(), PostType.FEED),
            "caption": self.caption_input.toPlainText().strip(),
            "approval_policy": approval_map.get(
                self.approval_combo.currentText(), ApprovalPolicy.MANUAL
            ),
            "schedule_policy": SchedulePolicy(
                policy_type=schedule_map.get(
                    self.schedule_combo.currentText(), SchedulePolicyType.IMMEDIATE
                )
            ),
            "notes": self.notes_input.toPlainText().strip(),
        }


class CampaignDetailPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.title_label = QLabel("Select a campaign")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(self.title_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 13px; color: #94a3b8;")
        layout.addWidget(self.status_label)

        self.caption_label = QLabel("")
        self.caption_label.setWordWrap(True)
        self.caption_label.setStyleSheet("font-size: 12px; color: #cbd5e1;")
        layout.addWidget(self.caption_label)

        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet("font-size: 12px; color: #64748b;")
        layout.addWidget(self.notes_label)

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        layout.addWidget(self.summary_label)

        self.target_model = TargetTableModel()
        self.target_table = CompactTable()
        self.target_table.setModel(self.target_model)
        if self.target_table.horizontalHeader():
            self.target_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch
            )
        layout.addWidget(self.target_table, stretch=1)

        # Action buttons
        action_bar = QHBoxLayout()
        self.btn_approve = SecondaryButton("Approve")
        self.btn_pause = SecondaryButton("Pause")
        self.btn_resume = SecondaryButton("Resume")
        self.btn_archive = SecondaryButton("Archive")
        action_bar.addWidget(self.btn_approve)
        action_bar.addWidget(self.btn_pause)
        action_bar.addWidget(self.btn_resume)
        action_bar.addWidget(self.btn_archive)
        action_bar.addStretch()
        layout.addLayout(action_bar)

    def set_campaign(self, campaign: Campaign | None) -> None:
        if campaign is None:
            self.title_label.setText("Select a campaign")
            self.status_label.setText("")
            self.caption_label.setText("")
            self.notes_label.setText("")
            self.summary_label.setText("")
            self.target_model.set_targets([])
            return

        color = STATUS_COLORS.get(campaign.status, "#94a3b8")
        self.title_label.setText(campaign.title)
        self.status_label.setText(
            f"Status: <span style='color:{color};'>"
            f"{campaign.status.value.replace('_', ' ').title()}</span>  |  "
            f"Type: {campaign.post_type.value.title()}  |  "
            f"Approval: {campaign.approval_policy.value.title()}"
        )
        self.caption_label.setText(campaign.caption or "(no caption)")
        self.notes_label.setText(f"Notes: {campaign.notes}" if campaign.notes else "")

        summary = campaign.generate_summary()
        self.summary_label.setText(
            f"Targets: {summary.total_targets}  |  "
            f"Success: {summary.successful_targets}  |  "
            f"Failed: {summary.failed_targets}  |  "
            f"Pending: {summary.pending_targets}  |  "
            f"Completion: {summary.completion_percentage}%"
        )
        self.target_model.set_targets(list(campaign.targets))


class CampaignWorkspace(QWidget):
    def __init__(
        self,
        campaign_service: "CampaignService",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._campaign_service = campaign_service
        self._selected_campaign: Campaign | None = None
        self._build_ui()
        self.reload_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # Top bar
        top_bar = QHBoxLayout()
        header_box = QVBoxLayout()
        title = QLabel("Campaign Manager")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        subtitle = QLabel("Multi-destination publishing campaigns with schedule and approval.")
        subtitle.setStyleSheet("color: #64748b; font-size: 12px;")
        header_box.addWidget(title)
        header_box.addWidget(subtitle)
        top_bar.addLayout(header_box)
        top_bar.addStretch()

        self.new_campaign_btn = PrimaryButton("+ New Campaign")
        self.new_campaign_btn.clicked.connect(self._on_new_campaign)
        top_bar.addWidget(self.new_campaign_btn)

        self.refresh_btn = SecondaryButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_data)
        top_bar.addWidget(self.refresh_btn)
        layout.addLayout(top_bar)

        # Metrics
        self.metrics = MetricRow(
            [
                ("Total", "0"),
                ("Running", "0"),
                ("Completed", "0"),
                ("Failed", "0"),
            ]
        )
        layout.addWidget(self.metrics)

        # Filter strip
        filter_strip = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search campaigns...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_strip.addWidget(self.search_input, stretch=2)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            [
                "All",
                "Draft",
                "Ready",
                "Waiting Approval",
                "Scheduled",
                "Running",
                "Paused",
                "Completed",
                "Partially Completed",
                "Failed",
            ]
        )
        self.status_filter.currentTextChanged.connect(self._on_status_filter)
        filter_strip.addWidget(self.status_filter)
        layout.addLayout(filter_strip)

        # Main splitter: Campaign list | Detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Campaign table
        self.campaign_model = CampaignTableModel()
        self.proxy_model = CampaignFilterProxyModel()
        self.proxy_model.setSourceModel(self.campaign_model)

        self.campaign_table = CompactTable()
        self.campaign_table.setModel(self.proxy_model)
        self.campaign_table.verticalHeader().setDefaultSectionSize(36)
        self.campaign_table.setSelectionBehavior(CompactTable.SelectionBehavior.SelectRows)
        self.campaign_table.setSelectionMode(CompactTable.SelectionMode.SingleSelection)
        if self.campaign_table.horizontalHeader():
            self.campaign_table.horizontalHeader().setSectionResizeMode(
                QHeaderView.ResizeMode.Stretch
            )
        if self.campaign_table.selectionModel():
            self.campaign_table.selectionModel().selectionChanged.connect(
                self._on_campaign_selected
            )
        splitter.addWidget(self.campaign_table)

        # Right: Detail panel
        self.detail_panel = CampaignDetailPanel()
        self.detail_panel.btn_approve.clicked.connect(self._on_approve)
        self.detail_panel.btn_pause.clicked.connect(self._on_pause)
        self.detail_panel.btn_resume.clicked.connect(self._on_resume)
        self.detail_panel.btn_archive.clicked.connect(self._on_archive)
        splitter.addWidget(self.detail_panel)
        splitter.setSizes([500, 400])

        layout.addWidget(splitter, stretch=1)

    def reload_data(self) -> None:
        campaigns = self._campaign_service.list_campaigns(include_archived=False)
        self.campaign_model.set_campaigns(campaigns)
        self._update_metrics(campaigns)

    def _update_metrics(self, campaigns: Sequence[Campaign]) -> None:
        total = len(campaigns)
        running = sum(1 for c in campaigns if c.status == CampaignStatus.RUNNING)
        completed = sum(1 for c in campaigns if c.status == CampaignStatus.COMPLETED)
        failed = sum(1 for c in campaigns if c.status == CampaignStatus.FAILED)
        if len(self.metrics.value_labels) >= 4:
            self.metrics.value_labels[0].setText(str(total))
            self.metrics.value_labels[1].setText(str(running))
            self.metrics.value_labels[2].setText(str(completed))
            self.metrics.value_labels[3].setText(str(failed))

    def _on_search_changed(self, text: str) -> None:
        self.proxy_model.set_search(text)

    def _on_status_filter(self, text: str) -> None:
        self.proxy_model.set_status_filter(text)

    def _on_campaign_selected(self) -> None:
        indexes = self.campaign_table.selectionModel().selectedRows()
        if not indexes:
            self._selected_campaign = None
            self.detail_panel.set_campaign(None)
            return
        source_index = self.proxy_model.mapToSource(indexes[0])
        campaign = self.campaign_model.get_campaign(source_index.row())
        self._selected_campaign = campaign
        self.detail_panel.set_campaign(campaign)

    def _on_new_campaign(self) -> None:
        dialog = NewCampaignDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            title = dialog.title_input.text().strip()
            if not title:
                QMessageBox.warning(self, "Validation", "Campaign title is required.")
                return
            post_type_map = {
                "Feed": PostType.FEED,
                "Reel": PostType.REEL,
                "Story": PostType.STORY,
            }
            approval_map = {
                "Manual": ApprovalPolicy.MANUAL,
                "Automatic": ApprovalPolicy.AUTOMATIC,
            }
            schedule_map = {
                "Immediate": SchedulePolicyType.IMMEDIATE,
                "Scheduled Once": SchedulePolicyType.SCHEDULED_ONCE,
                "Staggered": SchedulePolicyType.STAGGERED,
            }
            result = self._campaign_service.create_campaign(
                title=title,
                post_type=post_type_map.get(
                    dialog.post_type_combo.currentText(), PostType.FEED
                ),
                caption=dialog.caption_input.toPlainText().strip(),
                approval_policy=approval_map.get(
                    dialog.approval_combo.currentText(), ApprovalPolicy.MANUAL
                ),
                schedule_policy=SchedulePolicy(
                    policy_type=schedule_map.get(
                        dialog.schedule_combo.currentText(),
                        SchedulePolicyType.IMMEDIATE,
                    )
                ),
                notes=dialog.notes_input.toPlainText().strip(),
            )
            if result.is_success:
                self.reload_data()
            else:
                QMessageBox.warning(self, "Error", str(result.error))

    def _on_approve(self) -> None:
        if self._selected_campaign is None:
            return
        result = self._campaign_service.approve_campaign(self._selected_campaign.id)
        if result.is_success:
            self.reload_data()

    def _on_pause(self) -> None:
        if self._selected_campaign is None:
            return
        result = self._campaign_service.pause_campaign(self._selected_campaign.id)
        if result.is_success:
            self.reload_data()

    def _on_resume(self) -> None:
        if self._selected_campaign is None:
            return
        result = self._campaign_service.resume_campaign(self._selected_campaign.id)
        if result.is_success:
            self.reload_data()

    def _on_archive(self) -> None:
        if self._selected_campaign is None:
            return
        answer = QMessageBox.question(
            self,
            "Archive Campaign",
            f"Archive campaign '{self._selected_campaign.title}'?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            result = self._campaign_service.update_campaign_status(
                self._selected_campaign.id, CampaignStatus.ARCHIVED
            )
            if result.is_success:
                self.reload_data()
