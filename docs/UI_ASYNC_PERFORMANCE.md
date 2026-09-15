# UI Asynchronous Execution & Zero-Freeze Performance

## Zero Freeze Architecture

To ensure responsive desktop operation under heavy batch workloads, all IO-bound, network-bound, and emulator automation tasks execute completely off the Qt main thread.

```
Qt GUI Thread                      QThreadPool / Background Worker
+------------------------+         +-------------------------------------+
| User clicks 'Run'      | ------> | AsyncActionWorker.run()             |
| UI remains interactive |         |   - Batch target iteration          |
| Progress bar streams   | <------ |   - signals.progress.emit(pct, msg) |
| User can cancel job    | ------> |   - check _is_cancelled flag        |
| Completion message     | <------ |   - signals.finished.emit()         |
+------------------------+         +-------------------------------------+
```

## Non-Blocking Guarantees

1. **`AsyncActionWorker` (`QRunnable`)**:
   - Dispatches tasks using Qt's `QThreadPool.globalInstance()`.
   - Communicates status back via Qt signals (`started`, `progress`, `target_completed`, `finished`, `error`).
2. **Cooperative Cancellation**:
   - `cancel()` sets an internal flag.
   - Workers check cancellation between target processing loops and gracefully terminate resource acquisition.
3. **Modal Independence**:
   - Closing the `ContextActionDialog` does not abort or interrupt the worker thread.
   - Status updates are routed to notifications and system logs.
