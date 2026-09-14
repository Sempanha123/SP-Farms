param (
    [switch]$Binary = $true,
    [switch]$Wheel = $false
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if ($Wheel) {
        & ".\.venv\Scripts\python.exe" -m build
    }
    if ($Binary) {
        & ".\.venv\Scripts\python.exe" scripts/build_windows_dist.py
    }
} finally {
    Pop-Location
}
