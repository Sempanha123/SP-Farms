$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & ".\.venv\Scripts\python.exe" -m ruff check --fix .
    & ".\.venv\Scripts\python.exe" -m ruff format .
} finally {
    Pop-Location
}
