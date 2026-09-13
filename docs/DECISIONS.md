# Decisions

## Python compatibility baseline

The package requires Python 3.12 or newer and Ruff and mypy target Python 3.12 syntax. Bootstrap prefers Python 3.12 and falls back to another installed Python only when it is at least version 3.12, allowing development to continue when the preferred interpreter is unavailable.

## Source layout

The import package lives directly under `sp_farms/` to keep the Windows bootstrap and entry-point setup simple. Architectural layers remain separate subpackages.

## Composition and lifecycle

`sp_farms.bootstrap` is the composition root and the only layer that constructs concrete infrastructure. The UI receives an `ApplicationContext`; its idempotent `close()` method runs registered shutdown hooks in reverse order so resources unwind predictably.

## Configuration and diagnostics safety

Local TOML configuration is allowlisted to non-secret runtime settings; environment values override file values. Diagnostics bundles include runtime metadata and a second-pass redacted log copy, never environment variables, config files, vault content, or database content.
