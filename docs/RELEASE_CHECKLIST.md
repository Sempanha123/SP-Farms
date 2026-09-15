# Production Release Checklist for SP-Farms

This checklist outlines the required quality gates, security audits, and deployment steps before publishing an official SP-Farms release.

---

## 1. Pre-Release Verification

- [ ] **Clean Working Tree**: Ensure all feature branches are merged and working tree has no uncommitted changes.
- [ ] **Ruff Linter Pass**:
  ```powershell
  .\.venv\Scripts\python.exe -m ruff check .
  ```
- [ ] **Mypy Static Type Verification**:
  ```powershell
  .\.venv\Scripts\python.exe -m mypy sp_farms
  ```
- [ ] **Full Pytest Regression Suite**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest --cov=sp_farms
  ```
- [ ] **Architecture Isolation Check**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/test_architecture.py
  ```
- [ ] **Clean Database Migration Verification**:
  ```powershell
  .\.venv\Scripts\python.exe -c "from pathlib import Path; from sp_farms.infrastructure.database import Database, run_migrations; db = Database(Path('tmp_verify.db')); run_migrations(db, Path('migrations')); db.close(); Path('tmp_verify.db').unlink()"
  ```
- [ ] **Secret Scan**: Verify that `.env`, `.pem`, `.pfx`, `.key`, or any real token values are absent from git tracking:
  ```powershell
  git status --ignored
  ```

---

## 2. Version Bump & Metadata

- [ ] Update version in `pyproject.toml` (`[project] version = "X.Y.Z"`).
- [ ] Update version strings in `packaging_windows/windows_version_info.txt`:
  - `filevers=(X, Y, Z, 0)`
  - `prodvers=(X, Y, Z, 0)`
  - `FileVersion`, `ProductVersion`
- [ ] Update version constant in `packaging_windows/installer.iss` (`#define MyAppVersion "X.Y.Z"`).
- [ ] Update version string in `packaging_windows/installer.nsi` (`DisplayVersion "X.Y.Z"`).
- [ ] Generate fresh application icons if visual assets changed:
  ```powershell
  .\.venv\Scripts\python.exe scripts/generate_icons.py
  ```

---

## 3. Package & Smoke Test

- [ ] Build standalone distribution locally:
  ```powershell
  .\.venv\Scripts\python.exe scripts/build_windows_dist.py
  ```
- [ ] Verify executable launches and renders correctly:
  ```powershell
  .\dist\SP-Farms\SP-Farms.exe
  ```
- [ ] Verify test database and vault creation in `%APPDATA%\SP-Farms\`.
- [ ] Test upgrade and non-destructive uninstall behavior.

---

## 4. Tagging & Automated Release

1. Commit version bumps:
   ```bash
   git commit -am "chore(release): bump version to vX.Y.Z"
   ```
2. Create signed git tag:
   ```bash
   git tag -a vX.Y.Z -m "SP-Farms release vX.Y.Z"
   ```
3. Push commit and tag:
   ```bash
   git push origin main
   git push origin vX.Y.Z
   ```
4. Verify GitHub Actions release workflow execution at `.github/workflows/release.yml`.
5. Verify published release assets:
   - `sp_farms-X.Y.Z-py3-none-any.whl`
   - `sp_farms-X.Y.Z.tar.gz`
   - `SP-Farms-vX.Y.Z-win64.zip`
   - `SP-Farms-Setup-X.Y.Z.exe`
