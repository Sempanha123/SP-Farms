from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from sp_farms.app.widgets import (
    DestructiveButton,
    Panel,
    PrimaryButton,
    SecondaryButton,
    StatusChip,
)
from sp_farms.application.job_service import JobService
from sp_farms.domain.jobs import Job, JobState

COLUMNS = (
    "Status",
    "Job Type",
    "Target",
    "Device / ID",
    "Progress",
    "Attempts",
    "Created",
    "Last Error",
)


def _format_elapsed(created_at: datetime, now: datetime) -> str:
    diff = now - created_at
    total_seconds = max(0, int(diff.total_seconds()))
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours = minutes // 60
    rem_min = minutes % 60
    return f"{hours}h {rem_min:02d}m"


_ROOT_INDEX = QModelIndex()


class JobTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._jobs: list[Job] = []

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(self._jobs)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _ROOT_INDEX) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(COLUMNS)
        ):
            return COLUMNS[section]
        return None

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._jobs)):
            return None

        job = self._jobs[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return job

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return job.state.value.capitalize().replace("_", " ")
            if col == 1:
                return job.job_type
            if col == 2:
                return job.target_type
            if col == 3:
                return job.target_id
            if col == 4:
                return f"{job.progress}%"
            if col == 5:
                return f"{job.attempt_count}/{job.max_attempts}"
            if col == 6:
                return _format_elapsed(job.created_at, datetime.now(UTC))
            if col == 7:
                return job.error_message or "-"

        return None

    def set_jobs(self, jobs: Sequence[Job]) -> None:
        self.beginResetModel()
        self._jobs = list(jobs)
        self.endResetModel()

    def get_job(self, row: int) -> Job | None:
        if 0 <= row < len(self._jobs):
            return self._jobs[row]
        return None

    def find_job(self, job_id: str) -> Job | None:
        for job in self._jobs:
            if job.id == job_id:
                return job
        return None

    def counts_by_state(self) -> dict[str, int]:
        counts = {
            "all": len(self._jobs),
            "running": 0,
            "queued": 0,
            "waiting_approval": 0,
            "failed": 0,
            "completed": 0,
        }
        for j in self._jobs:
            if j.state is JobState.RUNNING:
                counts["running"] += 1
            elif j.state is JobState.QUEUED:
                counts["queued"] += 1
            elif j.state is JobState.WAITING_APPROVAL:
                counts["waiting_approval"] += 1
            elif j.state is JobState.FAILED:
                counts["failed"] += 1
            elif j.state is JobState.SUCCEEDED:
                counts["completed"] += 1
        return counts


class JobQueueFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filter_state: str = "all"
        self._search_term: str = ""

    def set_filter_state(self, state: str) -> None:
        self._filter_state = state.lower()
        self.invalidate()

    def set_search_term(self, term: str) -> None:
        self._search_term = term.strip().lower()
        self.invalidate()

    def filterAcceptsRow(
        self,
        source_row: int,
        source_parent: QModelIndex | QPersistentModelIndex,
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, JobTableModel):
            return True

        job = model.get_job(source_row)
        if job is None:
            return False

        if self._filter_state == "running" and job.state is not JobState.RUNNING:
            return False
        if self._filter_state == "queued" and job.state is not JobState.QUEUED:
            return False
        if self._filter_state == "waiting_approval" and job.state is not JobState.WAITING_APPROVAL:
            return False
        if self._filter_state == "failed" and job.state is not JobState.FAILED:
            return False
        if self._filter_state == "completed" and job.state is not JobState.SUCCEEDED:
            return False

        if self._search_term:
            query = self._search_term
            matches = (
                query in job.id.lower()
                or query in job.job_type.lower()
                or query in job.target_type.lower()
                or query in job.target_id.lower()
                or (job.error_message and query in job.error_message.lower())
            )
            if not matches:
                return False

        return True


class JobInspectorPanel(Panel):
    target_opened = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("jobInspectorPanel")
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("Job Inspector")
        header.setStyleSheet("font-size: 14px; font-weight: 650;")
        layout.addWidget(header)

        self._empty_label = QLabel(
            "Select a job to view detailed diagnostics and execution events."
        )
        self._empty_label.setWordWrap(True)
        self._empty_label.setProperty("muted", True)
        layout.addWidget(self._empty_label)

        self._detail_container = QWidget()
        detail_layout = QVBoxLayout(self._detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        self._status_chip = StatusChip("Ready", "neutral")
        detail_layout.addWidget(self._status_chip)

        self._type_label = QLabel()
        self._type_label.setStyleSheet("font-weight: 600;")
        detail_layout.addWidget(self._type_label)

        self._target_label = QLabel()
        detail_layout.addWidget(self._target_label)

        self._id_label = QLabel()
        self._id_label.setStyleSheet("font-size: 11px;")
        self._id_label.setProperty("muted", True)
        self._id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self._id_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setFixedHeight(12)
        detail_layout.addWidget(self._progress_bar)

        self._attempts_label = QLabel()
        detail_layout.addWidget(self._attempts_label)

        self._error_box = QTextEdit()
        self._error_box.setReadOnly(True)
        self._error_box.setMaximumHeight(90)
        self._error_box.setPlaceholderText("No errors reported.")
        detail_layout.addWidget(self._error_box)

        self._open_target_btn = SecondaryButton("Open Target")
        self._open_target_btn.clicked.connect(self._on_open_target)
        detail_layout.addWidget(self._open_target_btn)

        layout.addWidget(self._detail_container)
        layout.addStretch()

        self._detail_container.hide()
        self._current_job: Job | None = None

    def inspect_job(self, job: Job | None) -> None:
        self._current_job = job
        if job is None:
            self._empty_label.show()
            self._detail_container.hide()
            return

        self._empty_label.hide()
        self._detail_container.show()

        state_tones: dict[JobState, str] = {
            JobState.PENDING: "neutral",
            JobState.QUEUED: "neutral",
            JobState.RUNNING: "active",
            JobState.WAITING_APPROVAL: "warning",
            JobState.RETRYING: "warning",
            JobState.SUCCEEDED: "success",
            JobState.FAILED: "error",
            JobState.CANCELLED: "neutral",
        }
        self._status_chip.update_state(
            state=state_tones.get(job.state, "neutral"),
            text=job.state.value.capitalize().replace("_", " "),
        )

        self._type_label.setText(f"Type: {job.job_type}")
        self._target_label.setText(f"Target: {job.target_type} ({job.target_id})")
        self._id_label.setText(f"ID: {job.id}")
        self._progress_bar.setValue(job.progress)
        self._attempts_label.setText(f"Attempts: {job.attempt_count}/{job.max_attempts}")

        if job.error_message:
            self._error_box.setText(f"[{job.error_code or 'error'}] {job.error_message}")
        else:
            self._error_box.setText("No errors recorded.")

    def _on_open_target(self) -> None:
        if self._current_job is not None:
            self.target_opened.emit(self._current_job.target_type, self._current_job.target_id)


class JobQueueView(QWidget):
    open_target_requested = Signal(str, str)

    def __init__(
        self,
        job_service: JobService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("jobQueueView")
        self._service = job_service

        self.model = JobTableModel(self)
        self.proxy_model = JobQueueFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)

        self._build_ui()
        self._connect_signals()
        self._update_action_states()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Top Toolbar
        toolbar = Panel()
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(6)

        self.filter_group = QButtonGroup(self)
        self.filter_buttons: dict[str, QPushButton] = {}
        for key, text in (
            ("all", "All"),
            ("running", "Running"),
            ("queued", "Queued"),
            ("waiting_approval", "Waiting"),
            ("failed", "Failed"),
            ("completed", "Completed"),
        ):
            btn = QPushButton(text)
            btn.setCheckable(True)
            self.filter_group.addButton(btn)
            self.filter_buttons[key] = btn
            tb_layout.addWidget(btn)

        self.filter_buttons["all"].setChecked(True)

        tb_layout.addSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter jobs...")
        self.search_input.setMaximumWidth(220)
        tb_layout.addWidget(self.search_input)

        tb_layout.addStretch()

        # Action Buttons
        self.start_resume_btn = PrimaryButton("Start / Resume")
        self.cancel_btn = DestructiveButton("Cancel")
        self.retry_btn = SecondaryButton("Retry")
        self.open_target_btn = SecondaryButton("Open Target")

        tb_layout.addWidget(self.start_resume_btn)
        tb_layout.addWidget(self.retry_btn)
        tb_layout.addWidget(self.cancel_btn)
        tb_layout.addWidget(self.open_target_btn)

        root.addWidget(toolbar)

        # Splitter: Table (left) + Inspector (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("jobQueueSplitter")

        self.table = QTableView()
        self.table.setModel(self.proxy_model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("font-size: 12px;")
        splitter.addWidget(self.table)

        self.inspector = JobInspectorPanel()
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([750, 270])
        root.addWidget(splitter, stretch=1)

        # Bottom Summary Counters
        summary_panel = Panel()
        sp_layout = QHBoxLayout(summary_panel)
        sp_layout.setContentsMargins(10, 4, 10, 4)
        sp_layout.setSpacing(14)

        self.summary_labels: dict[str, QLabel] = {
            "all": QLabel("Total: 0"),
            "running": QLabel("Running: 0"),
            "queued": QLabel("Queued: 0"),
            "waiting_approval": QLabel("Waiting: 0"),
            "failed": QLabel("Failed: 0"),
            "completed": QLabel("Completed: 0"),
        }
        for lbl in self.summary_labels.values():
            sp_layout.addWidget(lbl)
        sp_layout.addStretch()

        root.addWidget(summary_panel)

    def _connect_signals(self) -> None:
        self.filter_group.buttonClicked.connect(self._on_filter_changed)
        self.search_input.textChanged.connect(self.proxy_model.set_search_term)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        self.start_resume_btn.clicked.connect(self._on_start_resume)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.retry_btn.clicked.connect(self._on_retry)
        self.open_target_btn.clicked.connect(self._on_open_target)
        self.inspector.target_opened.connect(self.open_target_requested)

    def set_jobs(self, jobs: Sequence[Job]) -> None:
        self.model.set_jobs(jobs)
        self._update_summary_counters()
        self._update_action_states()

    def _update_summary_counters(self) -> None:
        counts = self.model.counts_by_state()
        self.summary_labels["all"].setText(f"Total: {counts['all']}")
        self.summary_labels["running"].setText(f"Running: {counts['running']}")
        self.summary_labels["queued"].setText(f"Queued: {counts['queued']}")
        self.summary_labels["waiting_approval"].setText(f"Waiting: {counts['waiting_approval']}")
        self.summary_labels["failed"].setText(f"Failed: {counts['failed']}")
        self.summary_labels["completed"].setText(f"Completed: {counts['completed']}")

    def _on_filter_changed(self) -> None:
        for key, btn in self.filter_buttons.items():
            if btn.isChecked():
                self.proxy_model.set_filter_state(key)
                break

    def _selected_jobs(self) -> list[Job]:
        sel_model = self.table.selectionModel()
        if sel_model is None:
            return []
        rows = {idx.row() for idx in sel_model.selectedIndexes()}
        jobs: list[Job] = []
        for row in sorted(rows):
            proxy_idx = self.proxy_model.index(row, 0)
            source_idx = self.proxy_model.mapToSource(proxy_idx)
            job = self.model.get_job(source_idx.row())
            if job is not None:
                jobs.append(job)
        return jobs

    def _on_selection_changed(self) -> None:
        selected = self._selected_jobs()
        if len(selected) == 1:
            self.inspector.inspect_job(selected[0])
        else:
            self.inspector.inspect_job(None)
        self._update_action_states()

    def _update_action_states(self) -> None:
        selected = self._selected_jobs()
        if not selected:
            self.start_resume_btn.setEnabled(False)
            self.cancel_btn.setEnabled(False)
            self.retry_btn.setEnabled(False)
            self.open_target_btn.setEnabled(False)
            return

        can_start = any(j.state in (JobState.WAITING_APPROVAL, JobState.PENDING) for j in selected)
        can_cancel = any(not j.state.is_terminal for j in selected)
        can_retry = any(j.state in (JobState.FAILED, JobState.CANCELLED) for j in selected)
        can_open = len(selected) == 1

        self.start_resume_btn.setEnabled(can_start)
        self.cancel_btn.setEnabled(can_cancel)
        self.retry_btn.setEnabled(can_retry)
        self.open_target_btn.setEnabled(can_open)

    def _on_start_resume(self) -> None:
        if self._service is None:
            return
        for job in self._selected_jobs():
            if job.state in (JobState.WAITING_APPROVAL, JobState.PENDING):
                self._service.transition_job(job.id, JobState.QUEUED, "Queued by operator")
        self.set_jobs(self._service.list_active_jobs())

    def _on_cancel(self) -> None:
        if self._service is None:
            return
        for job in self._selected_jobs():
            if not job.state.is_terminal:
                self._service.cancel_job(job.id, "Cancelled by operator")
        self.set_jobs(self._service.list_active_jobs())

    def _on_retry(self) -> None:
        if self._service is None:
            return
        for job in self._selected_jobs():
            if job.state in (JobState.FAILED, JobState.CANCELLED):
                self._service.transition_job(job.id, JobState.QUEUED, "Retried by operator")
        self.set_jobs(self._service.list_active_jobs())

    def _on_open_target(self) -> None:
        selected = self._selected_jobs()
        if len(selected) == 1:
            self.open_target_requested.emit(selected[0].target_type, selected[0].target_id)
