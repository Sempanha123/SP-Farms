# Decisions

## Python compatibility baseline

The package requires Python 3.12 or newer and Ruff and mypy target Python 3.12 syntax. Bootstrap prefers Python 3.12 and falls back to another installed Python only when it is at least version 3.12, allowing development to continue when the preferred interpreter is unavailable.

## Source layout

The import package lives directly under `sp_farms/` to keep the Windows bootstrap and entry-point setup simple. Architectural layers remain separate subpackages.

## Composition and lifecycle

`sp_farms.bootstrap` is the composition root and the only layer that constructs concrete infrastructure. The UI receives an `ApplicationContext`; its idempotent `close()` method runs registered shutdown hooks in reverse order so resources unwind predictably.

## Configuration and diagnostics safety

Local TOML configuration is allowlisted to non-secret runtime settings; environment values override file values. Diagnostics bundles include runtime metadata and a second-pass redacted log copy, never environment variables, config files, vault content, or database content.

## Persistence and migrations

SQLite connections always use WAL, foreign keys, normal synchronous mode, and a busy timeout. Application services receive a unit-of-work factory rather than sessions. Startup runs Alembic to head; an existing database is copied before any revision-changing upgrade, while clean and current databases avoid redundant backups.

## Secret boundary

Sensitive values live only behind the vault port; Windows deployments use Credential Manager through `keyring`. SQLite and normal exports retain opaque random references plus metadata. Explicit transfer uses authenticated AES-256-GCM encryption with a scrypt-derived key and never persists the passphrase.

## Visual semantics

Shared widgets consume semantic light/dark palette tokens. Controls remain compact—30 px inputs and buttons, 34 px table rows, 8–10 px radii—with visible focus borders and textual state labels. This preserves the reference image’s dense desktop hierarchy without glow, glass, or generic dashboard spacing.

## Main shell ownership

The shell is a thin presentation container: top navigation, resizable device/content/queue columns, and compact status. `QSettings` owns local geometry and visibility preferences. Feature workspaces replace placeholders incrementally; the shell never opens database sessions or performs long-running work.

## Operator command registry

Navigation, palette entries, and global shortcuts share one command registry so all invocation paths run identical handlers. Registration rejects duplicate IDs and normalized shortcut collisions. Progress UI remains non-modal; notifications use a model that future persistent job events can feed.

## Durable job lifecycle

Long-running work is persisted as a current-state job plus append-only transition events. Domain code owns transition validity; application services own transactional orchestration; infrastructure owns mapping only. Optional unique idempotency keys collapse duplicate requests. Startup converts interrupted running work to retrying when attempts remain or failed otherwise, preserving explicit recovery markers and audit history.

## Worker supervisor concurrency and backoff

Background jobs run on a bounded worker pool behind an application supervisor. Concurrency limits protect both provider gateways and target accounts/devices from saturation. Execution handlers receive a cooperative cancellation token and progress reporter; unhandled exceptions are contained without crashing the supervisor. Failed attempts trigger exponential backoff with a UTC-based next retry timestamp until max attempts are exhausted.

## Operator job queue and presentation models

The operator job queue presentation relies on a clean Qt Model-View-Proxy architecture. `JobTableModel` handles dense tabular data with formatting and metrics caching, while `JobQueueFilterProxyModel` handles client-side filtering by job state and search queries without database re-queries. Inspector details and batch actions inspect current selection validity across multiple items, protecting terminal jobs from invalid commands while maintaining responsiveness on queues with thousands of entries.

## Device management projection and persistence

Provider discovery is projected into immutable `ManagedDevice` rows keyed by provider and stable ADB identity. Qt models consume those rows but never execute provider subprocesses; discovery and device actions run through `DeviceService` on worker threads. Alias and notes are durable domain profile data in SQLite, while saved filters remain local `QSettings` presentation preferences. Optional metrics remain absent rather than triggering one health-check subprocess per table row. Emulator window arrangement stays unavailable until the provider port exposes it uniformly.

## Account metadata and health

Accounts persist management metadata only; credentials, tokens, cookies, recovery codes, and 2FA seeds remain behind the vault boundary. Device assignments use provider plus external ID without a foreign key to transient discovery inventory. Archiving preserves categories, tags, and device relationships while normal listings exclude archived accounts. Health is a deterministic domain calculation over status, security, permissions, 2FA, verification, device assignment, and profile completeness.

## Account onboarding safety boundary

Account onboarding creates local management records for authorized existing accounts; it never automates platform signup. Manual and development/test sources accept validated metadata, while official login and permitted session attachment require configured connectors that return normalized metadata only. Imports use a strict versioned allowlist, recursively reject secret-bearing fields, and normal exports remain metadata-only. General account views mask email and phone values; credentials, cookies, tokens, and session material remain behind connector/vault boundaries.

## Account device profiles and restore workspace

Account-device environments are preserved through explicit `DeviceProfile` and `AccountDeviceBinding` records rather than synthetic runtime spoofing. The restore sequence executes an ordered 9-step verification workflow (binding resolution, emulator startup, ADB readiness, package presence validation, harmless preference application, app launch, security state verification, operator re-authentication request, and heartbeat/login updates). Spoofing hardware identities (IMEI, MAC, Android ID) or injecting auth tokens to bypass challenges is strictly prohibited; accounts in compromised, review-required, or revoked permission states are flagged for operator-assisted re-authentication. Non-blocking `_Worker` execution on `QThreadPool` keeps GUI interactions fluid during hardware/emulator discovery and app startup.

## QA profile isolation and reload bridge

Synthetic QA fixtures are stored in dedicated profile, target, assignment, and audit records; actual ADB/provider inventory is never mutated. All operations require an enabled exact package allowlist entry after a hard denylist check. Application/domain layers depend only on the versioned `QAProfileReloadBridge`, while infrastructure uses argument-array ADB push and fixed remote commands. Compatibility randomization is limited to harmless device-catalog fields; identity generation is excluded, while explicit authorized fixtures retain clearly marked `test_*` names. Bridge audits store no fixture values.

## ADB Abstraction and Discovery

Direct subprocess execution is strictly encapsulated behind the `AdbPort` protocol. Neither UI components nor higher-level automation services invoke the `adb` binary or parse command-line output directly. Executable resolution checks user overrides, environment variables, and standard Windows SDK paths. Stderr error categorization converts CLI error strings into typed domain exceptions (`AdbTimeoutError`, `AdbUnauthorizedError`, `AdbOfflineError`, `AdbDeviceNotFoundError`). Deterministic simulation through `FakeAdbAdapter` provides complete offline testability across device authorization and failure scenarios without hardware dependencies.

## LDPlayer Provider Integration

LDPlayer interaction is isolated behind `DeviceProviderPort`. The provider interfaces with `ldconsole.exe` / `dnconsole.exe` strictly for emulator process lifecycle (`launch`, `quit`, `reboot`, `runapp`), while relying on `AdbPort` for standard Android subsystem interactions (`screencap`, `logcat`, properties, package management). Device identity spoofing and anti-detection evasion techniques are strictly avoided; instances are mapped transparently via their standard port and serial ranges (`emulator-5554`, `emulator-5556`, etc.). Fake provider fixtures enable comprehensive offline testing of instance states, health monitoring, and error mapping without running virtualization software.

## MuMu Provider Integration

MuMu Player automation conforms to the unified `DeviceProviderPort` abstraction. Subprocess commands communicate with `MuMuManager.exe` using JSON API queries and player lifecycle actions (`launch_player`, `close_player`, `restart_player`, `launch_app`), with fallback to tabular line output parsing. ADB communication uses standard loopback ports (`127.0.0.1:{16384 + index * 32}`). Common diagnostics expose availability, executable paths, and instance metrics uniformly across providers, ensuring the operator interface can display mixed fleets of LDPlayer and MuMu instances without vendor-specific UI logic.

## Physical Android Provider Integration

Physical Android devices (connected via USB or Wi-Fi TCP/IP) conform to the identical `DeviceProviderPort` application protocol as virtual emulators. Hardware devices are classified by serial signature (distinguishing physical USB and Wi-Fi devices from emulator ports). Because physical devices cannot be cold-booted or shut down via software commands, remote power operations raise clear domain errors, while warm reboots, package installs, log collection, and screenshots execute uniformly via ADB. Hardware diagnostics capture device properties (`ro.product.model`, `ro.build.version.release`, etc.) and battery levels without hardware identity spoofing or tampering.

## Device Pool and Lightweight Workspace Snapshots

Device scheduling coordinates across available physical and virtual devices using explicit atomic reservations (`account_workspace_locks`) with TTL-based expiration and automatic stale lock reclaiming. Workspace snapshots (`.spws`) store only versioned, non-secret operator preferences and account metadata in compressed JSON archives. Platform disk images, app caches, private app data, raw cookies, and authentication secrets are strictly excluded, enforcing safety and keeping backup archives under 100 KB per account.

## Accounts Workspace and Dense Model-View Design

The accounts workspace follows a strict Model-View-Proxy separation: `QStandardItemModel` retains rich raw metadata across 24 columns, while `QSortFilterProxyModel` evaluates multiple orthogonal predicates (text search, category, device binding, and smart health filters) without re-querying the database. Bulk actions (categorization, tagging, device assignment, archive, and metadata export) operate on selection models in batch transactions, keeping the UI responsive even with 1,500+ accounts loaded.





