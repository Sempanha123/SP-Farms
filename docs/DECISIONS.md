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
