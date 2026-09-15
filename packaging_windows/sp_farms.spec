# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for SP-Farms Windows desktop application."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

root_dir = Path(__file__).resolve().parent.parent

# Collect data files
datas = [
    (str(root_dir / "assets"), "assets"),
    (str(root_dir / "sp_farms" / "infrastructure" / "persistence" / "alembic"), "sp_farms/infrastructure/persistence/alembic"),
]

# Hidden imports required by SQLAlchemy, PySide6, and system libraries
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "sp_farms",
    "sp_farms.app",
    "sp_farms.app.main",
    "sp_farms.domain",
    "sp_farms.application",
    "sp_farms.infrastructure",
    "sp_farms.modules",
    "sp_farms.plugins",
    "keyring.backends.Windows",
    "cryptography",
    "sqlite3",
    "sqlalchemy.dialects.sqlite",
    "alembic",
    "platformdirs",
    "httpx",
]

# Excluded packages to minimize distribution size and attack surface
excludes = [
    "tkinter",
    "unittest",
    "test",
    "tests",
    "pytest",
    "mypy",
    "ruff",
    "pre_commit",
    "pdb",
]

a = Analysis(
    [str(root_dir / "sp_farms" / "app" / "main.py")],
    pathex=[str(root_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SP-Farms",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Avoid UPX on Windows as it triggers anti-virus false positives
    console=False,  # Windowed GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root_dir / "assets" / "icons" / "sp_farms.ico"),
    version=str(root_dir / "packaging_windows" / "windows_version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SP-Farms",
)
