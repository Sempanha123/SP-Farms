# SP-Farms

SP-Farms is a Windows 11 desktop workspace for managing social assets that the operator owns or is explicitly authorized to manage. It uses official platform APIs where available and transparent, operator-approved Android automation where required.

## Requirements

- Windows 11
- Python 3.12 or newer
- PowerShell 7 or Windows PowerShell 5.1

## Bootstrap

```powershell
.\scripts\bootstrap.ps1
```

The script creates the repository-local `.venv` when needed, installs the project and development tools, and can be run repeatedly.

## Development

```powershell
.\scripts\dev.ps1
.\scripts\test.ps1
.\scripts\lint.ps1
.\scripts\format.ps1
```

The initial application entry point can also be run with:

```powershell
.\.venv\Scripts\python.exe -m sp_farms.app.main
```

## Safety

Do not use SP-Farms for accounts or assets without explicit authorization. The project does not support challenge bypass, identity spoofing, anti-detection behavior, credential theft, spam, or bulk engagement manipulation.
