# Persistent Jobs

Long-running operations are represented by domain `Job` records and append-only `JobEvent` audit records. Application services depend on `JobRepository` and `UnitOfWork` ports; only the SQLAlchemy adapter knows about SQLite.

## Lifecycle

A job starts as `pending` and follows validated transitions:

- `pending` → `queued` or `cancelled`
- `queued` → `running` or `cancelled`
- `running` → `waiting_approval`, `retrying`, `succeeded`, `failed`, or `cancelled`
- `waiting_approval` → `running` or `cancelled`
- `retrying` → `running`, `failed`, or `cancelled`
- Terminal states cannot transition.

Every creation and transition appends a timestamped event. Progress is constrained to 0–100. Optional idempotency keys prevent duplicate logical work.

## Restart recovery

At application startup, `JobService.recover_interrupted_jobs()` inspects active jobs. A job left `running` is marked `retrying` when attempts remain, otherwise `failed`; the recovery event and `app_restart_recovery` error marker are committed atomically with the job update. Queued, waiting-approval, and retrying jobs retain their durable states for their respective workers.
