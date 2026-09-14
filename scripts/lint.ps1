$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & ".\.venv\Scripts\python.exe" -m ruff check .
    & ".\.venv\Scripts\python.exe" -m ruff format --check .
    & ".\.venv\Scripts\python.exe" -m mypy sp_farms tests
} finally {
    Pop-Location
}
