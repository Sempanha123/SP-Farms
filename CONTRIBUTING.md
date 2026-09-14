# Contributing to SP-Farms

Thank you for contributing to SP-Farms. SP-Farms is a high-performance Windows 11 desktop application for managing operator-owned social assets.

---

## 1. Development Environment Setup

### Prerequisites
- Windows 11 (or Windows 10 x64)
- Python 3.12 (or 3.14)
- Git for Windows
- PowerShell 7+ or Git Bash

### Virtual Environment Setup
Run the bootstrap script or initialize manually:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Alternatively, run:
```powershell
.\scripts\bootstrap.ps1
```

---

## 2. Code Quality & Standards

SP-Farms maintains strict quality gates and architectural boundaries. Every change must pass:

### Linting (Ruff)
```powershell
.\.venv\Scripts\python.exe -m ruff check .
```

### Type Checking (Mypy)
```powershell
.\.venv\Scripts\python.exe -m mypy sp_farms
```

### Automated Tests (Pytest)
```powershell
.\.venv\Scripts\python.exe -m pytest
```

Or use the provided PowerShell helpers:
```powershell
.\scripts\lint.ps1
.\scripts\test.ps1
.\scripts\format.ps1
```

---

## 3. Architecture Rules

1. **Hexagonal Boundaries**:
   - UI (`sp_farms.app`) must **never** import database models or infrastructure directly.
   - UI interacts exclusively through application services and ports on `ApplicationContext`.
   - Domain (`sp_farms.domain`) never imports outer layers.
2. **Platform & Safety Rules**:
   - Never implement CAPTCHA bypass, checkpoint bypass, or anti-detect fingerprint rotation.
   - Never commit plaintext secrets, `.pfx` certificates, or API tokens.
3. **No UI Thread Blocking**:
   - Long-running disk, device, or network tasks must be executed asynchronously via worker threads or `JobService`.

---

## 4. Local Packaging Build

To test the Windows packaging locally:
```powershell
.\.venv\Scripts\python.exe scripts/build_windows_dist.py
```
The output will be placed in `dist/SP-Farms/`.
