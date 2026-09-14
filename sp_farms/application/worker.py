import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Lock, Thread
from typing import Protocol

from sp_farms.application.job_service import JobService
from sp_farms.application.ports import Clock
from sp_farms.domain.jobs import Job, JobState, calculate_backoff

logger = logging.getLogger(__name__)


class CancellationToken:
    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise JobCancelledError("Job execution cancelled")


class JobCancelledError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ConcurrencyLimits:
    max_total_workers: int = 4
    max_per_provider: int = 2
    max_per_target: int = 1


@dataclass(frozen=True, slots=True)
class WorkerHeartbeat:
    worker_id: str
    job_id: str | None
    last_seen_at: datetime


class JobExecutionContext:
    def __init__(
        self,
        job: Job,
        token: CancellationToken,
        service: JobService,
        clock: Clock,
        heartbeat_callback: Callable[[], None],
    ) -> None:
        self.job = job
        self.cancellation_token = token
        self._service = service
        self._clock = clock
        self._heartbeat_callback = heartbeat_callback

    @property
    def is_cancelled(self) -> bool:
        return self.cancellation_token.is_cancelled

    def check_cancelled(self) -> None:
        self.cancellation_token.raise_if_cancelled()

    def record_progress(self, progress: int) -> None:
        self.check_cancelled()
        self._service.record_progress(self.job.id, progress)
        self.heartbeat()

    def heartbeat(self) -> None:
        self._heartbeat_callback()


class JobHandler(Protocol):
    def __call__(self, context: JobExecutionContext, /) -> None: ...


class FakeStressJobHandler:
    def __init__(
        self,
        steps: int = 5,
        step_delay_seconds: float = 0.0,
        fail_at_step: int | None = None,
        error_message: str = "Injected synthetic failure",
    ) -> None:
        self.steps = steps
        self.step_delay_seconds = step_delay_seconds
        self.fail_at_step = fail_at_step
        self.error_message = error_message

    def __call__(self, context: JobExecutionContext) -> None:
        for step in range(1, self.steps + 1):
            context.check_cancelled()
            if self.fail_at_step is not None and step == self.fail_at_step:
                raise RuntimeError(self.error_message)
            percent = int((step / self.steps) * 100)
            context.record_progress(percent)
            if self.step_delay_seconds > 0:
                time.sleep(self.step_delay_seconds)


class WorkerSupervisor:
    def __init__(
        self,
        job_service: JobService,
        clock: Clock,
        limits: ConcurrencyLimits | None = None,
    ) -> None:
        self._service = job_service
        self._clock = clock
        self._limits = limits or ConcurrencyLimits()
        self._handlers: dict[str, JobHandler] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=self._limits.max_total_workers,
            thread_name_prefix="sp-worker",
        )
        self._lock = Lock()
        self._running_jobs: dict[str, tuple[str, str]] = {}
        self._cancellation_tokens: dict[str, CancellationToken] = {}
        self._heartbeats: dict[str, WorkerHeartbeat] = {}
        self._futures: dict[str, Future[None]] = {}
        self._stop_event = Event()
        self._poller_thread: Thread | None = None

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        with self._lock:
            self._handlers[job_type] = handler

    def start(self, poll_interval_seconds: float = 0.5) -> None:
        with self._lock:
            if self._poller_thread is not None and self._poller_thread.is_alive():
                return
            self._stop_event.clear()
            self._poller_thread = Thread(
                target=self._run_loop,
                args=(poll_interval_seconds,),
                daemon=True,
                name="sp-supervisor-loop",
            )
            self._poller_thread.start()

    def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        with self._lock:
            tokens = list(self._cancellation_tokens.values())
        for token in tokens:
            token.cancel()

        if self._poller_thread is not None and self._poller_thread.is_alive():
            self._poller_thread.join(timeout=timeout_seconds)

        self._executor.shutdown(wait=True, cancel_futures=True)

    def cancel_job(self, job_id: str, reason: str = "Cancelled by operator") -> bool:
        with self._lock:
            token = self._cancellation_tokens.get(job_id)
            if token is not None:
                token.cancel()
        try:
            self._service.cancel_job(job_id, reason)
            return True
        except ValueError:
            return False

    def list_heartbeats(self) -> tuple[WorkerHeartbeat, ...]:
        with self._lock:
            return tuple(self._heartbeats.values())

    def tick(self) -> int:
        with self._lock:
            if self._stop_event.is_set():
                return 0
            slots_available = self._limits.max_total_workers - len(self._running_jobs)
            if slots_available <= 0:
                return 0

        dispatched = 0
        runnable = self._service.list_runnable_jobs()
        for job in runnable:
            if not self._can_dispatch(job):
                continue

            token = CancellationToken()
            with self._lock:
                self._running_jobs[job.id] = (job.target_type, job.target_id)
                self._cancellation_tokens[job.id] = token

            try:
                self._service.transition_job(job.id, JobState.RUNNING, "Dispatched to worker")
            except Exception as e:
                with self._lock:
                    self._running_jobs.pop(job.id, None)
                    self._cancellation_tokens.pop(job.id, None)
                logger.error("Failed to transition job %s to running: %s", job.id, e)
                continue

            future = self._executor.submit(self._execute_job, job.id, token)
            with self._lock:
                self._futures[job.id] = future
            dispatched += 1

            with self._lock:
                if len(self._running_jobs) >= self._limits.max_total_workers:
                    break

        return dispatched

    def _can_dispatch(self, job: Job) -> bool:
        with self._lock:
            if job.id in self._running_jobs:
                return False
            if len(self._running_jobs) >= self._limits.max_total_workers:
                return False

            provider_count = sum(
                1 for t_type, _ in self._running_jobs.values() if t_type == job.target_type
            )
            if provider_count >= self._limits.max_per_provider:
                return False

            target_count = sum(
                1 for _, t_id in self._running_jobs.values() if t_id == job.target_id
            )
            return target_count < self._limits.max_per_target

    def _execute_job(self, job_id: str, token: CancellationToken) -> None:
        worker_id = f"worker-{job_id[:8]}"
        self._record_heartbeat(worker_id, job_id)

        job = self._service.get_job(job_id)
        if job is None:
            self._cleanup_job(job_id, worker_id)
            return

        with self._lock:
            handler = self._handlers.get(job.job_type)

        if handler is None:
            self._service.transition_job(
                job_id=job.id,
                new_state=JobState.FAILED,
                message=f"No handler registered for type '{job.job_type}'",
                error_code="no_handler",
                error_message=f"Missing handler: {job.job_type}",
            )
            self._cleanup_job(job_id, worker_id)
            return

        ctx = JobExecutionContext(
            job=job,
            token=token,
            service=self._service,
            clock=self._clock,
            heartbeat_callback=lambda: self._record_heartbeat(worker_id, job_id),
        )

        try:
            if token.is_cancelled:
                raise JobCancelledError("Cancelled before start")

            handler(ctx)

            if token.is_cancelled:
                raise JobCancelledError("Cancelled during execution")

            self._service.transition_job(
                job_id=job.id,
                new_state=JobState.SUCCEEDED,
                message="Completed successfully",
            )
        except JobCancelledError:
            self._service.cancel_job(job.id, "Execution cancelled")
        except Exception as exc:
            logger.exception("Job %s raised exception: %s", job.id, exc)
            self._handle_failure(job, str(exc))
        finally:
            self._cleanup_job(job_id, worker_id)

    def _handle_failure(self, job: Job, error_message: str) -> None:
        now = self._clock.now()
        fresh = self._service.get_job(job.id) or job
        attempts = fresh.record_attempt()
        if attempts < fresh.max_attempts:
            delay = calculate_backoff(attempts)
            next_retry = now + delay
            delay_sec = delay.total_seconds()
            msg = f"Failed attempt {attempts}/{fresh.max_attempts}. Retry in {delay_sec:.1f}s"
            self._service.transition_job(
                job_id=fresh.id,
                new_state=JobState.RETRYING,
                message=msg,
                error_code="execution_failure",
                error_message=error_message,
                next_retry_at=next_retry,
                attempt_count=attempts,
            )
        else:
            self._service.transition_job(
                job_id=fresh.id,
                new_state=JobState.FAILED,
                message=f"Failed after {attempts} attempts",
                error_code="max_attempts_exceeded",
                error_message=error_message,
                attempt_count=attempts,
            )

    def _record_heartbeat(self, worker_id: str, job_id: str | None) -> None:
        with self._lock:
            self._heartbeats[worker_id] = WorkerHeartbeat(
                worker_id=worker_id,
                job_id=job_id,
                last_seen_at=self._clock.now(),
            )

    def _cleanup_job(self, job_id: str, worker_id: str) -> None:
        with self._lock:
            self._running_jobs.pop(job_id, None)
            self._cancellation_tokens.pop(job_id, None)
            self._futures.pop(job_id, None)
            self._heartbeats[worker_id] = WorkerHeartbeat(
                worker_id=worker_id,
                job_id=None,
                last_seen_at=self._clock.now(),
            )

    def _run_loop(self, poll_interval_seconds: float) -> None:
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.error("Supervisor tick error: %s", e)
            self._stop_event.wait(poll_interval_seconds)
