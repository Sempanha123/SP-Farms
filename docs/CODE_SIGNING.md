# Code Signing & Packaging Guide for SP-Farms

This guide outlines the production packaging and Authenticode code-signing configuration for SP-Farms Windows 11 releases.

---

## 1. Upgrade-Safe Data Topology

SP-Farms binaries are installed to:
- `%ProgramFiles%\SP-Farms\` (or `%LocalAppData%\Programs\SP-Farms` for per-user installations).

All operator and user data is isolated from the binary installation directory to ensure safe updates and clean reinstalls:
- **Application Database**: `%APPDATA%\SP-Farms\sp_farms.db` (SQLite WAL)
- **Local Vault / Encrypted Tokens**: `%APPDATA%\SP-Farms\vault\`
- **Backups / Snapshots**: `%APPDATA%\SP-Farms\backups\`
- **Logs**: `%LOCALAPPDATA%\SP-Farms\sp_farms.log`

### Uninstaller Policy
When updating or uninstalling SP-Farms:
- The binary files, desktop shortcuts, and start menu entries are removed.
- **User databases, vault files, and `.spbackup` snapshots are retained by default** to prevent accidental data loss.
- A purge of user data is only performed if the operator explicitly selects "Delete all user databases, backups, and saved configurations" during uninstallation.

---

## 2. Reproducible Packaging with PyInstaller

Package creation is fully automated via `scripts/build_windows_dist.py` and `packaging/sp_farms.spec`:

```powershell
.\.venv\Scripts\python.exe scripts/build_windows_dist.py
```

This generates:
- `dist/SP-Farms/`: A standalone Windows bundle containing `SP-Farms.exe`, embedded Qt plugins (platforms, styles, SVG icon engines), Alembic migrations, and high-resolution icons.

---

## 3. Authenticode Code Signing

SP-Farms supports code signing via Windows SDK `signtool.exe` without inventing certificates or committing credentials to source control.

### Configuration via Environment Variables

To sign releases during CI/CD or production builds, configure the following environment variables:

| Variable | Description | Example |
|---|---|---|
| `SP_FARMS_CERT_PATH` | Path to your Authenticode `.pfx` file | `C:\Certs\sp_farms_codesign.pfx` |
| `SP_FARMS_CERT_PASSWORD` | Password for the `.pfx` certificate | *(Injected via CI secret)* |
| `SP_FARMS_TIMESTAMP_URL` | RFC 3161 Timestamping authority | `http://timestamp.digicert.com` |
| `SP_FARMS_DIGEST_ALGORITHM` | Hash algorithm for signature | `sha256` (default) |
| `SP_FARMS_SIGNTOOL_PATH` | Explicit path to `signtool.exe` (optional) | `C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe` |
| `SP_FARMS_SIGN_DRY_RUN` | Test signing flow without certificate | `1` |

### Dry Run Verification
To verify the signing workflow locally without a production hardware token or certificate:
```powershell
$env:SP_FARMS_SIGN_DRY_RUN = "1"
.\.venv\Scripts\python.exe scripts/build_windows_dist.py
```

### Hardware Token / Azure Trusted Signing
For hardware HSM tokens (YubiKey, Nitrokey) or cloud signing (Azure Trusted Signing), specify the custom signing command or provider in `packaging/signing.py`.

---

## 4. Compiling the Windows Installer

### Inno Setup (Recommended)
1. Install [Inno Setup 6+](https://jrsoftware.org/isdl.php).
2. Compile the installer script:
   ```cmd
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
   ```
3. Artifact is saved to: `dist\installer\SP-Farms-Setup-0.1.0.exe`.

### NSIS Alternative
1. Install [NSIS 3+](https://nsis.sourceforge.io/).
2. Compile:
   ```cmd
   makensis packaging\installer.nsi
   ```
3. Artifact is saved to: `dist\installer\SP-Farms-Setup-0.1.0-nsis.exe`.
