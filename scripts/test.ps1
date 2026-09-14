$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    & ".\.venv\Scripts\python.exe" -m pytest --cov=sp_farms --cov-report=term-missing @args
} finally {
    Pop-Location
}
