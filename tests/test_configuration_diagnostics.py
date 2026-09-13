import json
import logging
import zipfile
from pathlib import Path

from sp_farms.infrastructure.config import load_config
from sp_farms.infrastructure.diagnostics import create_diagnostics_bundle
from sp_farms.infrastructure.logging import configure_logging, get_logger, redact


def test_config_precedence(tmp_path: Path) -> None:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[sp_farms]\nenvironment = "file"\nlog_level = "warning"\nlog_max_bytes = 128\n',
        encoding="utf-8",
    )

    config = load_config(
        config_file,
        {
            "SP_FARMS_ENV": "test",
            "SP_FARMS_LOG_LEVEL": "debug",
            "SP_FARMS_DATABASE_PATH": str(tmp_path / "data.db"),
            "SP_FARMS_LOG_PATH": str(tmp_path / "app.log"),
        },
    )

    assert config.environment == "test"
    assert config.log_level == "DEBUG"
    assert config.log_max_bytes == 128
    assert config.database_path == tmp_path / "data.db"


def test_secret_redaction() -> None:
    message = (
        "password=hunter2 token: abc.def authorization=Bearer top-secret "
        "Cookie=session-value recovery_code=123456"
    )

    output = redact(message)

    for secret in ("hunter2", "abc.def", "top-secret", "session-value", "123456"):
        assert secret not in output
    assert output.count("[REDACTED]") == 5


def test_rotation_configuration_and_structured_output(tmp_path: Path) -> None:
    config = load_config(
        environ={
            "SP_FARMS_LOG_PATH": str(tmp_path / "app.log"),
            "SP_FARMS_LOG_MAX_BYTES": "256",
            "SP_FARMS_LOG_BACKUP_COUNT": "2",
        }
    )
    handler = configure_logging(config)
    get_logger("test").warning("authorization: Bearer private-value")
    handler.flush()

    assert handler.maxBytes == 256
    assert handler.backupCount == 2
    record = json.loads(config.log_path.read_text(encoding="utf-8"))
    assert record["level"] == "WARNING"
    assert "private-value" not in record["message"]

    logging.getLogger("sp_farms").handlers.clear()
    handler.close()


def test_diagnostics_bundle_excludes_secrets(tmp_path: Path) -> None:
    log_path = tmp_path / "app.log"
    log_path.write_text(
        "password=not-safe authorization: Bearer also-not-safe\n",
        encoding="utf-8",
    )
    config = load_config(
        environ={
            "SP_FARMS_DATABASE_PATH": str(tmp_path / "data.db"),
            "SP_FARMS_LOG_PATH": str(log_path),
        }
    )

    output = create_diagnostics_bundle(
        tmp_path / "diagnostics.zip",
        config,
        {"adb": "unavailable"},
    )

    with zipfile.ZipFile(output) as bundle:
        contents = "\n".join(bundle.read(name).decode("utf-8") for name in bundle.namelist())
    assert "not-safe" not in contents
    assert "also-not-safe" not in contents
    assert "[REDACTED]" in contents
    assert '"adb": "unavailable"' in contents
