# Progress

## Phase 01 — Repository Bootstrap and Local `.venv`

Status: complete

- Created Python package metadata and the `sp-farms` console entry point.
- Added repository hygiene, local configuration template, and development tooling.
- Added idempotent PowerShell workflows for bootstrap, development, tests, linting, formatting, and packaging.
- Added package, entry-point, bootstrap, and virtual-environment exclusion tests.
- Reused the working repository-local `.venv`; Python 3.12 was detected by the launcher but its installation is unavailable, so local validation uses Python 3.14 while the project targets Python 3.12+.
