import time
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from sp_farms.app.job_queue import JobQueueView, JobTableModel
from sp_farms.domain.jobs import Job, JobState


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app  # type: ignore[return-value]


def _make_job(
    job_id: str,
    state: JobState,
    job_type: str = "warmup",
    target_type: str = "account",
    target_id: str = "acc_1",
    progress: int = 0,
    attempt_count: int = 0,
    max_attempts: int = 3,
    error_message: str | None = None,
) -> Job:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    return Job(
        id=job_id,
        job_type=job_type,
        target_type=target_type,
        target_id=target_id,
        state=state,
        progress=progress,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        idempotency_key=None,
        error_code="err" if error_message else None,
        error_message=error_message,
        next_retry_at=None,
        created_at=now,
        updated_at=now,
    )


def test_job_table_model_data_and_counts(qapp: QApplication) -> None:
    model = JobTableModel()
    jobs = [
        _make_job("j1", JobState.RUNNING, progress=50),
        _make_job("j2", JobState.QUEUED),
        _make_job("j3", JobState.WAITING_APPROVAL),
        _make_job("j4", JobState.FAILED, error_message="Network dropped"),
        _make_job("j5", JobState.SUCCEEDED, progress=100),
    ]
    model.set_jobs(jobs)

    assert model.rowCount() == 5
    assert model.columnCount() == 8

    # Row 0: RUNNING
    assert model.data(model.index(0, 0)) == "Running"
    assert model.data(model.index(0, 1)) == "warmup"
    assert model.data(model.index(0, 2)) == "account"
    assert model.data(model.index(0, 3)) == "acc_1"
    assert model.data(model.index(0, 4)) == "50%"
    assert model.data(model.index(0, 7)) == "-"

    # Row 3: FAILED
    assert model.data(model.index(3, 0)) == "Failed"
    assert model.data(model.index(3, 7)) == "Network dropped"

    counts = model.counts_by_state()
    assert counts["all"] == 5
    assert counts["running"] == 1
    assert counts["queued"] == 1
    assert counts["waiting_approval"] == 1
    assert counts["failed"] == 1
    assert counts["completed"] == 1


def test_filter_proxy_model_by_state_and_search(qapp: QApplication) -> None:
    view = JobQueueView()
    jobs = [
        _make_job("j1", JobState.RUNNING, job_type="sync_contacts", target_id="acc_10"),
        _make_job("j2", JobState.QUEUED, job_type="post_feed", target_id="acc_20"),
        _make_job("j3", JobState.FAILED, job_type="sync_contacts", target_id="acc_30"),
        _make_job("j4", JobState.SUCCEEDED, job_type="backup", target_id="acc_40"),
    ]
    view.set_jobs(jobs)

    # Initial: all 4 visible
    assert view.proxy_model.rowCount() == 4

    # Filter by Running
    view.filter_buttons["running"].click()
    assert view.proxy_model.rowCount() == 1

    # Filter by Failed
    view.filter_buttons["failed"].click()
    assert view.proxy_model.rowCount() == 1

    # Filter by All + Search text
    view.filter_buttons["all"].click()
    assert view.proxy_model.rowCount() == 4

    view.search_input.setText("contacts")
    assert view.proxy_model.rowCount() == 2  # j1 and j3

    view.search_input.setText("acc_40")
    assert view.proxy_model.rowCount() == 1  # j4


def _row_for_job_id(view: JobQueueView, job_id: str) -> int:
    for row in range(view.proxy_model.rowCount()):
        idx = view.proxy_model.index(row, 0)
        src = view.proxy_model.mapToSource(idx)
        job = view.model.get_job(src.row())
        if job and job.id == job_id:
            return row
    return -1


def test_action_buttons_enablement(qapp: QApplication) -> None:
    view = JobQueueView()
    j_pending = _make_job("j1", JobState.PENDING)
    j_running = _make_job("j2", JobState.RUNNING)
    j_failed = _make_job("j3", JobState.FAILED)
    j_succeeded = _make_job("j4", JobState.SUCCEEDED)

    view.set_jobs([j_pending, j_running, j_failed, j_succeeded])

    # No selection
    view.table.clearSelection()
    assert not view.start_resume_btn.isEnabled()
    assert not view.cancel_btn.isEnabled()
    assert not view.retry_btn.isEnabled()
    assert not view.open_target_btn.isEnabled()

    # Select Pending
    row_pending = _row_for_job_id(view, "j1")
    view.table.selectRow(row_pending)
    assert view.start_resume_btn.isEnabled()
    assert view.cancel_btn.isEnabled()
    assert not view.retry_btn.isEnabled()
    assert view.open_target_btn.isEnabled()

    # Select Running
    row_running = _row_for_job_id(view, "j2")
    view.table.selectRow(row_running)
    assert not view.start_resume_btn.isEnabled()
    assert view.cancel_btn.isEnabled()
    assert not view.retry_btn.isEnabled()
    assert view.open_target_btn.isEnabled()

    # Select Failed
    row_failed = _row_for_job_id(view, "j3")
    view.table.selectRow(row_failed)
    assert not view.start_resume_btn.isEnabled()
    assert not view.cancel_btn.isEnabled()
    assert view.retry_btn.isEnabled()
    assert view.open_target_btn.isEnabled()

    # Multi-select (Running + Failed)
    sel_model = view.table.selectionModel()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    sel_model.select(view.proxy_model.index(row_running, 0), flags)
    sel_model.select(view.proxy_model.index(row_failed, 0), flags)

    assert view.cancel_btn.isEnabled()  # from running
    assert view.retry_btn.isEnabled()  # from failed
    assert not view.open_target_btn.isEnabled()  # multi-select disables single open


def test_inspector_updates_on_selection(qapp: QApplication) -> None:
    view = JobQueueView()
    job = _make_job(
        "job-abc",
        JobState.FAILED,
        job_type="device_flash",
        target_type="device",
        target_id="dev-99",
        progress=45,
        error_message="USB disconnect error",
    )
    view.set_jobs([job])

    # Nothing selected initially
    assert view.inspector._detail_container.isHidden()

    view.table.selectRow(0)
    assert not view.inspector._detail_container.isHidden()
    assert "device_flash" in view.inspector._type_label.text()
    assert "dev-99" in view.inspector._target_label.text()
    assert "job-abc" in view.inspector._id_label.text()
    assert view.inspector._progress_bar.value() == 45
    assert "USB disconnect error" in view.inspector._error_box.toPlainText()


def test_large_queue_responsiveness(qapp: QApplication) -> None:
    view = JobQueueView()
    total_jobs = 1500
    states = [JobState.QUEUED, JobState.RUNNING, JobState.SUCCEEDED, JobState.FAILED]
    large_list = [
        _make_job(
            f"job-{i}",
            states[i % len(states)],
            job_type=f"type_{i % 5}",
            target_id=f"target_{i % 20}",
        )
        for i in range(total_jobs)
    ]

    start_time = time.perf_counter()
    view.set_jobs(large_list)
    load_duration = time.perf_counter() - start_time

    assert view.proxy_model.rowCount() == total_jobs
    # Should load 1500 items in well under 1 second
    assert load_duration < 1.0

    # Filter performance
    start_filter = time.perf_counter()
    view.filter_buttons["running"].click()
    filter_duration = time.perf_counter() - start_filter
    assert filter_duration < 0.5
    assert view.proxy_model.rowCount() == total_jobs // 4
