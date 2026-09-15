$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $Preferred = Get-Command py -ErrorAction SilentlyContinue
    if ($Preferred) {
        & py -3.12 -m venv (Join-Path $Root ".venv")
    } else {
        & python -m venv (Join-Path $Root ".venv")
    }
}

$Version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ([version]$Version -lt [version]"3.12") {
    throw "SP-Farms requires Python 3.12 or newer; found $Version."
}

Push-Location $Root
try {
    & $Python -m pip install --upgrade pip setuptools wheel
    & $Python -m pip install --editable ".[dev]"
} finally {
    Pop-Location
}
