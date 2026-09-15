from pathlib import Path

from sp_farms.application.packaging import (
    InstallationPaths,
    purge_user_data_if_requested,
    resolve_installation_paths,
    should_preserve_data_on_uninstall,
)
from sp_farms.infrastructure.signing import SigningConfig, find_signtool, sign_executable


def test_resolve_installation_paths() -> None:
    paths = resolve_installation_paths()
    assert isinstance(paths, InstallationPaths)
    assert paths.data_dir.name == "SP-Farms"
    assert paths.database_file.name == "sp_farms.db"
    assert paths.backup_dir.name == "backups"
    assert paths.vault_dir.name == "vault"


def test_uninstall_data_preservation_policy() -> None:
    # By default, without explicit request, user data must be preserved
    assert should_preserve_data_on_uninstall(explicit_purge_requested=False) is True
    # Only if explicit purge requested should it not preserve data
    assert should_preserve_data_on_uninstall(explicit_purge_requested=True) is False


def test_purge_user_data_if_requested_safety(tmp_path: Path) -> None:
    dummy_data_dir = tmp_path / "appdata" / "SP-Farms"
    dummy_log_dir = tmp_path / "localappdata" / "SP-Farms"
    dummy_data_dir.mkdir(parents=True)
    dummy_log_dir.mkdir(parents=True)
    db_file = dummy_data_dir / "sp_farms.db"
    db_file.write_text("dummy database content")

    paths = InstallationPaths(
        data_dir=dummy_data_dir,
        log_dir=dummy_log_dir,
        database_file=db_file,
        backup_dir=dummy_data_dir / "backups",
        vault_dir=dummy_data_dir / "vault",
    )

    # When explicit_purge_requested is False, data is preserved untouched
    purged = purge_user_data_if_requested(paths, explicit_purge_requested=False)
    assert purged is False
    assert db_file.exists()

    # When explicit_purge_requested is True, user data is removed
    purged = purge_user_data_if_requested(paths, explicit_purge_requested=True)
    assert purged is True
    assert not dummy_data_dir.exists()


def test_signing_config_from_environment() -> None:
    environ = {
        "SP_FARMS_CERT_PATH": r"C:\certs\test.pfx",
        "SP_FARMS_CERT_PASSWORD": "secret_password",
        "SP_FARMS_TIMESTAMP_URL": "http://timestamp.test.com",
        "SP_FARMS_DIGEST_ALGORITHM": "sha384",
        "SP_FARMS_SIGN_DRY_RUN": "1",
    }
    cfg = SigningConfig.from_environment(environ)
    assert cfg.cert_path == Path(r"C:\certs\test.pfx")
    assert cfg.cert_password == "secret_password"
    assert cfg.timestamp_url == "http://timestamp.test.com"
    assert cfg.digest_algorithm == "sha384"
    assert cfg.dry_run is True


def test_sign_executable_dry_run(tmp_path: Path) -> None:
    target_exe = tmp_path / "SP-Farms.exe"
    target_exe.write_bytes(b"dummy executable bytes")

    cfg = SigningConfig(dry_run=True, digest_algorithm="sha256")
    success, message = sign_executable(target_exe, cfg)
    assert success is True
    assert "[DRY-RUN]" in message


def test_sign_executable_missing_target(tmp_path: Path) -> None:
    target_exe = tmp_path / "NonExistent.exe"
    cfg = SigningConfig(dry_run=True)
    success, message = sign_executable(target_exe, cfg)
    assert success is False
    assert "Target file does not exist" in message


def test_sign_executable_missing_cert_returns_skipped(tmp_path: Path) -> None:
    target_exe = tmp_path / "SP-Farms.exe"
    target_exe.write_bytes(b"dummy exe")

    # When no cert is provided and dry_run is False
    cfg = SigningConfig(cert_path=None, dry_run=False)
    success, message = sign_executable(target_exe, cfg)
    assert success is False
    assert "not configured" in message


def test_find_signtool_custom_path(tmp_path: Path) -> None:
    custom_tool = tmp_path / "custom_signtool.exe"
    custom_tool.write_bytes(b"fake tool")
    found = find_signtool(custom_tool)
    assert found == custom_tool


def test_spec_and_installer_files_exist() -> None:
    root = Path(__file__).resolve().parent.parent
    spec_path = root / "packaging_windows" / "sp_farms.spec"
    iss_path = root / "packaging_windows" / "installer.iss"
    nsi_path = root / "packaging_windows" / "installer.nsi"
    version_path = root / "packaging_windows" / "windows_version_info.txt"
    icon_path = root / "assets" / "icons" / "sp_farms.ico"

    assert spec_path.exists()
    assert iss_path.exists()
    assert nsi_path.exists()
    assert version_path.exists()
    assert icon_path.exists()
