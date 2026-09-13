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
