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

## Phase 15 — Physical Android Provider

Status: complete

- Extended domain models with `ConnectionTransport` (USB, Wi-Fi, Emulator), `PhysicalDeviceMetadata` (manufacturer, brand, model, Android OS version, SDK version, battery level, battery charging, resolution), and `TroubleshootingGuidance`.
- Extended `DeviceProviderPort` application protocol with `install_apk()` and `get_troubleshooting()` methods across all provider implementations.
- Added transport classifier distinguishing USB hardware, local network Wi-Fi devices, and loopback/emulators.
- Added battery parser extracting percentage and charging states from `dumpsys battery`.
- Added contextual operator troubleshooting guidance for unauthorized, offline, bootloader, and unconfigured device states.
- Implemented `PhysicalAndroidProvider` discovering physical USB and Wi-Fi devices, pulling hardware metadata, launching apps, installing APK packages, capturing screenshots, collecting logcat, and running diagnostics.
- Implemented `FakePhysicalProvider` with simulated USB and Wi-Fi physical devices, battery state tracking, APK installation simulation, and failure injection.
- Integrated `PhysicalAndroidProvider` into `ApplicationContext` and application bootstrap.
- Added tests for transport classification, battery parsing, lifecycle limitations, metadata queries, APK installation, offline/unauthorized troubleshooting, and diagnostic metrics.

## Phase 16 — Device Manager Workspace

Status: complete

- Added a unified device service aggregating LDPlayer, MuMu, and physical endpoints while isolating unavailable providers.
- Added a dense model/view device table with provider, identity, state, Android, assignment, app, resource, network, resolution, and heartbeat columns.
- Added live search, provider/state filters, persistent saved filter presets, multi-select, and select-all.
- Added capability-aware start, stop, restart, app launch, screenshot, and log actions on background workers.
- Connected the account workspace rail and Devices page to one shared device model.
- Added durable device aliases and notes through SQLite profile persistence and Alembic migration 0004.
- Kept optional emulator window arrangement disabled because no unified provider capability exists.
- Added mixed-provider, action-state, persistence, filter, artifact, and 1,500-device performance tests.

## Phase 17 — LSPosed QA Device Profile Lab and Hot Reload

Status: complete

- Added isolated, versioned QA profile records with explicit `test_*` fixture fields; actual device inventory remains unchanged.
- Added persistent authorized-package allowlists, per-device QA assignments, and masked operation audits through migration 0005.
- Enforced package syntax, authorization notes, denylist-before-allowlist checks, and refusal of known social, payment, banking, authenticator, and integrity targets.
- Added strict JSON import/export plus safe compatibility-only catalog randomization; identity generators are intentionally excluded.
- Added an abstract reload bridge with safe ADB argument-array push, mode `600`, remote verification, versioned acknowledgement, typed failures, guaranteed temporary-file cleanup, and restore-default behavior.
- Added a Devices tab containing the three-pane QA Profile Lab, profile editor, package authorization, bridge state, assignment, and background push/reload/verify/restore actions.
- Added domain, persistence, denylist, ADB cleanup, permission, bridge, assignment, and UI smoke coverage.
- Documented operator scope and the version 1 module contract in `docs/QA_DEVICE_PROFILE_LAB.md` and `docs/LSPOSED_QA_BRIDGE.md`.

## Phase 18 — Account Domain Rich Metadata

Status: complete

- Added rich account, category, tag, and stable provider-device assignment domain models.
- Persisted profile, contact, lifecycle, status, 2FA indicator, grouping, app preference, activity counts, permission state, and security state metadata through migration 0006.
- Added account CRUD, category/tag assignment, device reassignment, deterministic health scoring, and archive-by-default application services.
- Kept credentials, tokens, cookies, recovery codes, and 2FA seeds outside account persistence behind the existing vault boundary.
- Added repository round-trip, category/tag, assignment, health-rule, and archive-preservation coverage.

## Phase 19 — Account Onboarding Workspace

Status: complete

- Replaced the demo account table with a live Accounts workspace backed by `AccountService`, including masked email/phone presentation, search, metrics, and immediate selection of newly added records.
- Added safe manual, development/test, strict versioned metadata-import, official connector, and permitted authorized-session onboarding boundaries without implementing account creation or challenge bypass.
- Added normalized metadata validation for required fields, contact details, dates, timestamps, enums, counts, lengths, and distinct recovery email.
- Added metadata-only JSON export and recursive rejection of secret-bearing or unknown import fields.
- Added persistent-mailbox guidance, supported preferred-app choices, success actions, and navigation routing to existing workspaces/placeholders.
- Added service, validation, import/export, masking, UI smoke, immediate availability, and success-routing coverage.

