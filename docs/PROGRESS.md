# Progress

## Phase 01 — Repository Bootstrap and Local `.venv`

Status: complete

- Created Python package metadata and the `sp-farms` console entry point.
- Added repository hygiene, local configuration template, and development tooling.
- Added idempotent PowerShell workflows for bootstrap, development, tests, linting, formatting, and packaging.
- Added package, entry-point, bootstrap, and virtual-environment exclusion tests.
- Reused the working repository-local `.venv`; Python 3.12 was detected by the launcher but its installation is unavailable, so local validation uses Python 3.14 while the project targets Python 3.12+.

## Phase 02 — Architecture Boundaries and Application Bootstrap

Status: complete

- Added domain, application, infrastructure, module, plugin, and application packages.
- Added shared result/error types and repository, service, provider, and clock protocols.
- Added the composition root, minimal application context, and idempotent clean shutdown hooks.
- Added architecture boundary, package import, result, bootstrap, and lifecycle tests.
- Documented allowed dependency directions in `docs/ARCHITECTURE.md`.

## Phase 03 — Configuration Logging and Diagnostics

Status: complete

- Added typed, validated non-secret configuration with defaults, TOML files, and environment precedence.
- Added rotating JSON logs, module logger helpers, and automatic sensitive-value redaction.
- Added runtime diagnostics and redacted ZIP support bundles without configuration, vault, or database contents.
- Wired log lifecycle into application composition and documented support workflows.
- Added tests for configuration precedence, rotation, structured output, redaction, and bundle safety.

## Phase 04 — SQLite SQLAlchemy and Alembic

Status: complete

- Added SQLAlchemy 2.x engine/session composition with SQLite WAL, foreign keys, safe sync, and busy timeout pragmas.
- Added UUID and lifecycle timestamp entity mapping plus an initial metadata table migration.
- Added application unit-of-work protocol and infrastructure transaction implementation.
- Added startup Alembic migration execution and pre-upgrade database backup behavior.
- Added clean-install, idempotent migration, WAL, commit, and rollback tests.

## Phase 05 — Secure Vault and Secret References

Status: complete

- Added a vault port and Windows Credential Manager-compatible keyring adapter.
- Added secret types, references, metadata-only persistence, and a migration with no plaintext columns.
- Added explicit AES-256-GCM secret archive transfer using scrypt-derived operator passphrases.
- Added a clipboard reveal helper that clears unchanged secrets after a timeout.
- Added fake-keyring, SQLite exclusion, safe export, encrypted round-trip, and clipboard tests.

## Phase 06 — SP-Farms Cute Design System

Status: complete

- Added semantic light/dark palettes and a compact PySide6 application style sheet.
- Added shared panel, primary button, status chip, empty-state, compact-table, and metric components.
- Added the offscreen-capable design-system preview for both themes.
- Added focus, selection, typography, density, radius, and status-color standards.
- Added offscreen render and component semantic tests.

## Phase 07 — Main Shell and Demo-Style Workspace Layout

Status: complete

- Added the responsive main window with compact top navigation and nine primary workspaces.
- Added the reference-style Device Manager rail, dense central management workspace, optional Job Queue drawer, and bottom status row.
- Added persisted window geometry, theme, and queue visibility through `QSettings`.
- Connected the real PySide6 event loop and clean application-context shutdown.
- Added offscreen shell rendering, navigation, splitter, queue, and geometry persistence tests.

## Phase 08 — Navigation, Command Palette, Shortcuts, Notifications

Status: complete

- Added a central command/navigation registry with duplicate ID and shortcut collision checks.
- Added searchable keyboard-first command palette and shortcut help dialog.
- Added Alt+1–9 route shortcuts plus Ctrl+K and Ctrl+/ global actions.
- Added notification-center model, dismissible toasts, and non-modal progress overlay.
- Added route execution, filtering, collision, notification, and overlay tests.

## Phase 09 — Persistent Job Domain and Schema

Status: complete

- Added durable job and append-only event domain entities with validated state transitions and progress bounds.
- Added application repository ports and transactional job creation, transition, idempotency, and restart-recovery services.
- Added SQLAlchemy mappings, repository adapter, indexed SQLite schema, and Alembic migration.
- Added persistence, transition audit, idempotency, database reopen, and interrupted-job recovery tests.
- Documented job lifecycle and recovery behavior in `docs/JOBS.md`.

## Phase 10 — Worker Supervisor and Execution Runtime

Status: complete

- Added bounded thread pool worker supervisor with thread-safe cancellation tokens and execution contexts.
- Added per-provider and per-target concurrency limit enforcement with tick-based deterministic dispatch.
- Added exponential backoff calculations, automatic retry scheduling, and max-attempt failure transitions.
- Added worker heartbeat tracking, synthetic fake/stress handlers, exception containment, and graceful shutdown.
- Wired startup recovery and supervisor shutdown hooks into `create_application`.
- Added tests for execution progress, cancellation, retry/backoff, concurrency limits, exception containment, and graceful shutdown.

## Phase 11 — Job Queue UI

Status: complete

- Added dense job queue table model (`JobTableModel`) and filtering/sorting proxy model (`JobQueueFilterProxyModel`).
- Added status filters: All, Running, Queued, Waiting Approval, Failed, Completed, plus case-insensitive text search.
- Added operator actions: Start/Resume, Cancel, Retry, Open Target with dynamic enablement based on single and multi-selection states.
- Added detailed side inspector (`JobInspectorPanel`) displaying progress, attempt metrics, formatted errors, target details, and status chips.
- Added bottom status counters for active, queued, failed, and completed workloads.
- Embedded `JobQueueView` in `MainWindow` under the Automation workspace.
- Added tests for table model sorting/filtering, selection action enablement, inspector updates, and large queue (1,500 items) responsiveness.

## Phase 12 — ADB Abstraction and Device Discovery

Status: complete

- Added `DeviceInfo` and `DeviceState` domain entities for physical and virtual Android endpoints.
- Added `AdbPort` application protocol and typed exceptions: `AdbTimeoutError`, `AdbDeviceNotFoundError`, `AdbUnauthorizedError`, and `AdbOfflineError`.
- Added Windows and cross-platform ADB executable locator with environment variable, user configuration, Android SDK, and PATH discovery.
- Added robust output parsing for `adb devices -l`, Android system properties (`ro.build.version.release`, `ro.build.version.sdk`), and display metrics (`wm size`).
- Implemented `SubprocessAdbClient` with timeout enforcement, process management, and error string categorization.
- Implemented `FakeAdbAdapter` with configurable `SimulatedDevice` fixtures for offline, unauthorized, timeout, and error state testing without hardware.
- Integrated ADB client into application bootstrap context with non-secret `adb_path` configuration support.
- Added comprehensive tests for device parsing, timeout mapping, unauthorized/offline states, locator precedence, and fake fixtures.

## Phase 13 — LDPlayer Provider

Status: complete

- Added `DeviceProviderType`, `ProviderCapabilities`, and `EmulatorInstance` domain models.
- Added `DeviceProviderPort` application protocol and typed exceptions: `ProviderExecutableNotFoundError`, `ProviderInstanceNotFoundError`, `ProviderOperationTimeoutError`.
- Added Windows LDPlayer locator discovering `ldconsole.exe` / `dnconsole.exe` across configuration, environment variables, PATH, and standard 64-bit/32-bit install paths.
- Added `ldconsole list2` parser extracting instance index, name, running status, PID, VBox PID, display resolution, DPI, and ADB serial mapping (`emulator-5554`, `emulator-5556`, etc.).
- Implemented `LdPlayerProvider` integrating subprocess execution for `launch`, `quit`, `reboot`, and `runapp`, coupled with `AdbPort` for screenshots, logcat, and health checks.
- Implemented `FakeLdPlayerProvider` with simulated instances, lifecycle management, mock screenshot binary generation, logcat simulation, and failure injection.
- Integrated LDPlayer provider into `ApplicationContext` and application bootstrap with non-secret `ldplayer_path` configuration support.
- Added tests for serial mapping, `list2` parsing, instance lifecycle, screenshot capture, log collection, locator precedence, and CLI error handling.

## Phase 14 — MuMu Provider

Status: complete

- Extended `DeviceProviderPort` application protocol with `diagnostics()` providing structured instance counts, execution availability, and ADB connectivity metadata.
- Added Windows MuMu locator discovering `MuMuManager.exe` / `mumu.exe` across configuration, environment variables, PATH, and standard 64-bit/32-bit install paths.
- Added MuMu instance parser supporting both JSON API outputs (`MuMuManager.exe api -v all`) and tabular line outputs, with base port mapping (`127.0.0.1:{16384 + index * 32}`) and custom port overrides.
- Implemented `MuMuProvider` integrating `launch_player`, `close_player`, `restart_player`, `launch_app`, and diagnostics with `AdbPort` delegation for screenshots, logcat, and health checks.
- Implemented `FakeMuMuProvider` with simulated instances, lifecycle management, mock screenshot generation, logcat simulation, and failure injection.
- Integrated MuMu provider into `ApplicationContext` and application bootstrap with non-secret `mumu_path` configuration support.
- Added tests for serial mapping, JSON/tabular parsing, lifecycle operations, app launch, screenshot capture, diagnostics, and CLI error handling.



