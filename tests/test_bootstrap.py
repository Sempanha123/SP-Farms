from pathlib import Path

import sp_farms

ROOT = Path(__file__).resolve().parents[1]


def test_package_import() -> None:
    assert sp_farms.__version__ == "1.0.0"


def test_bootstrap_script_is_idempotent_by_design() -> None:
    script = (ROOT / "scripts" / "bootstrap.ps1").read_text(encoding="utf-8")
    assert "Test-Path $Python" in script
    assert 'pip install --editable ".[dev]"' in script


def test_virtual_environment_is_ignored() -> None:
    patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".venv/" in patterns
