"""Scheduler and Calendar workspace UI supporting Day/Week/Month/Agenda views and queue controls."""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from PySide6.QtCore import (
    QAbstractTableModel,
    QDate,
    QDateTime,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    QTime,
    Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import CompactTable, MetricRow, PrimaryButton, SecondaryButton
from sp_farms.application.scheduler_service import SchedulerService
from sp_farms.domain.composer import PostType, PublishDestinationType
from sp_farms.domain.scheduler import (
    ScheduledItem,
    ScheduledItemStatus,
    SchedulePriority,
)

logger = logging.getLogger(__name__)


class ScheduledItemTableModel(QAbstractTableModel):
    HEADERS = ["Time (UTC)", "Title", "Destination", "Type", "Status", "Priority", "Retries"]

    def __init__(self, items: Sequence[ScheduledItem] = ()) -> None:
        super().__init__()
        self._items: list[ScheduledItem] = list(items)

    def set_items(self, items: Sequence[ScheduledItem]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:
        return len(self._items)

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
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        item = self._items[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return item.scheduled_at.strftime("%Y-%m-%d %H:%M")
            if col == 1:
                return item.title
            if col == 2:
                return f"{item.destination_name} ({item.destination_type.value})"
            if col == 3:
                return item.post_type.value.upper()
            if col == 4:
                return item.status.value.upper()
            if col == 5:
                return item.priority.value.upper()
            if col == 6:
                return f"{item.retry_count}/{item.max_retries}"

        return None

    def get_item(self, row: int) -> ScheduledItem | None:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None


class RescheduleDialog(QDialog):
    def __init__(self, item: ScheduledItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Reschedule: {item.title}")
        self.resize(360, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.time_edit = QDateTimeEdit()
        self.time_edit.setDateTime(
            QDateTime(
                QDate(
                    item.scheduled_at.year,
                    item.scheduled_at.month,
                    item.scheduled_at.day,
                ),
                QTime(
                    item.scheduled_at.hour,
                    item.scheduled_at.minute,
                    item.scheduled_at.second,
                ),
            )
        )
        self.time_edit.setCalendarPopup(True)
        self.time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        form.addRow("New Scheduled Time:", self.time_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_datetime(self) -> datetime:
        qdt = self.time_edit.dateTime()
        return datetime(
            qdt.date().year(),
            qdt.date().month(),
            qdt.date().day(),
            qdt.time().hour(),
            qdt.time().minute(),
            qdt.time().second(),
            tzinfo=UTC,
        )


class NewScheduleDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Schedule New Post")
        self.resize(450, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        form.addRow("Title:", self.title_edit)

        self.dest_type_combo = QComboBox()
        for dt in PublishDestinationType:
            self.dest_type_combo.addItem(dt.value.capitalize(), dt.value)
        form.addRow("Destination Type:", self.dest_type_combo)

        self.dest_name_edit = QLineEdit("Farm Account #1")
        form.addRow("Destination Name:", self.dest_name_edit)

        self.dest_id_edit = QLineEdit("acc-001")
        form.addRow("Destination ID:", self.dest_id_edit)

        self.post_type_combo = QComboBox()
        for pt in PostType:
            self.post_type_combo.addItem(pt.value.capitalize(), pt.value)
        form.addRow("Post Type:", self.post_type_combo)

        self.priority_combo = QComboBox()
        for p in SchedulePriority:
            self.priority_combo.addItem(p.value.capitalize(), p.value)
        self.priority_combo.setCurrentText("Normal")
        form.addRow("Priority:", self.priority_combo)

        default_time = datetime.now(UTC) + timedelta(hours=1)
        self.time_edit = QDateTimeEdit()
        self.time_edit.setDateTime(
            QDateTime(
                QDate(default_time.year, default_time.month, default_time.day),
                QTime(default_time.hour, default_time.minute, default_time.second),
            )
        )
        self.time_edit.setCalendarPopup(True)
        self.time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        form.addRow("Schedule Time:", self.time_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_datetime(self) -> datetime:
        qdt = self.time_edit.dateTime()
        return datetime(
            qdt.date().year(),
            qdt.date().month(),
            qdt.date().day(),
            qdt.time().hour(),
            qdt.time().minute(),
            qdt.time().second(),
            tzinfo=UTC,
        )


class SchedulerWorkspace(QWidget):
    """Full-featured publishing calendar and schedule queue manager."""

    item_selected = Signal(str)

    def __init__(
        self,
        scheduler_service: SchedulerService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scheduler_service = scheduler_service

        self._view_mode = "month"
        self._current_date = datetime.now(UTC)

        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Top Control Bar
        top_bar = QHBoxLayout()

        # View Switcher (Day, Week, Month, Agenda)
        self.view_group = QButtonGroup(self)
        self.day_btn = QRadioButton("Day")
        self.week_btn = QRadioButton("Week")
        self.month_btn = QRadioButton("Month")
        self.month_btn.setChecked(True)
        self.agenda_btn = QRadioButton("Agenda")

        self.view_group.addButton(self.day_btn)
        self.view_group.addButton(self.week_btn)
        self.view_group.addButton(self.month_btn)
        self.view_group.addButton(self.agenda_btn)

        self.day_btn.toggled.connect(lambda: self._on_view_changed("day"))
        self.week_btn.toggled.connect(lambda: self._on_view_changed("week"))
        self.month_btn.toggled.connect(lambda: self._on_view_changed("month"))
        self.agenda_btn.toggled.connect(lambda: self._on_view_changed("agenda"))

        view_box = QHBoxLayout()
        view_box.addWidget(QLabel("View:"))
        view_box.addWidget(self.day_btn)
        view_box.addWidget(self.week_btn)
        view_box.addWidget(self.month_btn)
        view_box.addWidget(self.agenda_btn)
        top_bar.addLayout(view_box)

        top_bar.addSpacing(20)

        # Date Navigation
        self.prev_btn = SecondaryButton("◄")
        self.prev_btn.setFixedWidth(32)
        self.prev_btn.clicked.connect(self._prev_period)
        self.next_btn = SecondaryButton("►")
        self.next_btn.setFixedWidth(32)
        self.next_btn.clicked.connect(self._next_period)
        self.period_label = QLabel()
        self.period_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        top_bar.addWidget(self.prev_btn)
        top_bar.addWidget(self.period_label)
        top_bar.addWidget(self.next_btn)

        top_bar.addStretch()

        # Action Buttons
        self.pause_btn = SecondaryButton("Pause Queue")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.recover_btn = SecondaryButton("Recover Missed")
        self.recover_btn.clicked.connect(self._recover_missed)
        self.schedule_btn = PrimaryButton("+ Schedule Post")
        self.schedule_btn.clicked.connect(self._on_new_schedule)

        top_bar.addWidget(self.pause_btn)
        top_bar.addWidget(self.recover_btn)
        top_bar.addWidget(self.schedule_btn)

        main_layout.addLayout(top_bar)

        # Metrics Row
        self.metrics = MetricRow(
            [("Scheduled", "0"), ("Queued", "0"), ("Running", "0"), ("Conflicts", "0")]
        )
        main_layout.addWidget(self.metrics)

        # Conflict Banner
        self.conflict_banner = QLabel()
        self.conflict_banner.setStyleSheet(
            "background-color: #ffebee; color: #c62828; "
            "padding: 6px 12px; border-radius: 4px; font-weight: bold;"
        )
        self.conflict_banner.hide()
        main_layout.addWidget(self.conflict_banner)

        # Splitter: Table & Details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table
        self.table_model = ScheduledItemTableModel()
        self.table = CompactTable()
        self.table.setModel(self.table_model)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.clicked.connect(self._on_table_select)
        splitter.addWidget(self.table)

        # Right Action Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(10)

        right_layout.addWidget(QLabel("<b>Actions & Rescheduling</b>"))

        self.reschedule_btn = SecondaryButton("Reschedule Selected")
        self.reschedule_btn.clicked.connect(self._reschedule_selected)
        right_layout.addWidget(self.reschedule_btn)

        self.cancel_btn = SecondaryButton("Cancel Selected")
        self.cancel_btn.clicked.connect(self._cancel_selected)
        right_layout.addWidget(self.cancel_btn)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _on_view_changed(self, mode: str) -> None:
        self._view_mode = mode
        self.refresh()

    def _prev_period(self) -> None:
        if self._view_mode == "day":
            self._current_date -= timedelta(days=1)
        elif self._view_mode == "week":
            self._current_date -= timedelta(days=7)
        elif self._view_mode == "month":
            self._current_date = (self._current_date.replace(day=1) - timedelta(days=1)).replace(
                day=1
            )
        else:
            self._current_date -= timedelta(days=30)
        self.refresh()

    def _next_period(self) -> None:
        if self._view_mode == "day":
            self._current_date += timedelta(days=1)
        elif self._view_mode == "week":
            self._current_date += timedelta(days=7)
        elif self._view_mode == "month":
            self._current_date = (self._current_date.replace(day=28) + timedelta(days=5)).replace(
                day=1
            )
        else:
            self._current_date += timedelta(days=30)
        self.refresh()

    def _toggle_pause(self) -> None:
        if self.scheduler_service.is_paused:
            self.scheduler_service.resume_all()
            self.pause_btn.setText("Pause Queue")
        else:
            self.scheduler_service.pause_all()
            self.pause_btn.setText("Resume Queue")
        self.refresh()

    def _recover_missed(self) -> None:
        recovered = self.scheduler_service.recover_missed_tasks()
        QMessageBox.information(
            self,
            "Missed Task Recovery",
            f"Successfully recovered and requeued {len(recovered)} missed task(s).",
        )
        self.refresh()

    def _on_table_select(self, index: QModelIndex) -> None:
        item = self.table_model.get_item(index.row())
        if item:
            self.item_selected.emit(item.id)

    def _on_new_schedule(self) -> None:
        dialog = NewScheduleDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            title = dialog.title_edit.text().strip()
            if not title:
                QMessageBox.warning(self, "Validation Error", "Title cannot be empty")
                return

            dest_type = PublishDestinationType(dialog.dest_type_combo.currentData())
            post_type = PostType(dialog.post_type_combo.currentData())
            priority = SchedulePriority(dialog.priority_combo.currentData())
            sched_time = dialog.get_datetime()

            result = self.scheduler_service.schedule_post(
                title=title,
                destination_type=dest_type,
                destination_id=dialog.dest_id_edit.text(),
                destination_name=dialog.dest_name_edit.text(),
                scheduled_at=sched_time,
                post_type=post_type,
                priority=priority,
            )

            if not result.is_success:
                QMessageBox.critical(
                    self, "Scheduling Failed", result.error.message if result.error else "Error"
                )
            else:
                self.refresh()

    def _reschedule_selected(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            QMessageBox.information(self, "Select Item", "Please select an item to reschedule.")
            return
        item = self.table_model.get_item(idx.row())
        if not item:
            return

        dialog = RescheduleDialog(item, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_dt = dialog.get_datetime()
            res = self.scheduler_service.reschedule_item(item.id, new_dt)
            if not res.is_success:
                QMessageBox.critical(
                    self, "Reschedule Failed", res.error.message if res.error else "Error"
                )
            else:
                self.refresh()

    def _cancel_selected(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        item = self.table_model.get_item(idx.row())
        if not item:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel '{item.title}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.scheduler_service.cancel_item(item.id)
            self.refresh()

    def refresh(self) -> None:
        # Update period label
        if self._view_mode == "day":
            self.period_label.setText(self._current_date.strftime("%B %d, %Y"))
        elif self._view_mode == "week":
            start = self._current_date - timedelta(days=self._current_date.weekday())
            end = start + timedelta(days=6)
            self.period_label.setText(f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}")
        elif self._view_mode == "month":
            self.period_label.setText(self._current_date.strftime("%B %Y"))
        else:
            self.period_label.setText("Upcoming 30 Days")

        items = self.scheduler_service.list_calendar_items(
            view_mode=self._view_mode,
            reference_date=self._current_date,
        )
        self.table_model.set_items(items)

        # Update metrics
        scheduled_count = len(items)
        queued_count = sum(1 for i in items if i.status == ScheduledItemStatus.QUEUED)
        running_count = sum(1 for i in items if i.status == ScheduledItemStatus.RUNNING)

        conflicts = self.scheduler_service.get_conflicts()
        conflict_count = len(conflicts)

        if len(self.metrics.value_labels) >= 4:
            self.metrics.value_labels[0].setText(str(scheduled_count))
            self.metrics.value_labels[1].setText(str(queued_count))
            self.metrics.value_labels[2].setText(str(running_count))
            self.metrics.value_labels[3].setText(str(conflict_count))

        if conflict_count > 0:
            self.conflict_banner.setText(
                f"⚠ Warning: {conflict_count} schedule conflict(s) detected! "
                "Posts scheduled within 10 min window on same destination."
            )
            self.conflict_banner.show()
        else:
            self.conflict_banner.hide()
