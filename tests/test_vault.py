import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from sp_farms.application.secret_service import SecretService
from sp_farms.application.vault import reveal_temporarily
from sp_farms.domain.secrets import SecretType
from sp_farms.infrastructure.database import Database, SecretMetadata, run_migrations
from sp_farms.infrastructure.vault import (
    EncryptedSecretArchive,
    KeyringVault,
    decrypt_secret,
    encrypt_secret,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[service, username] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        self.values.pop((service, username), None)


class FakeClipboard:
    def __init__(self) -> None:
        self.value = ""

    def text(self) -> str:
        return self.value

    def set_text(self, value: str) -> None:
        self.value = value


class FakeScheduler:
    def __init__(self) -> None:
        self.callback: Any = None
        self.delay = 0.0

    def schedule(self, delay_seconds: float, callback: Any) -> None:
        self.delay = delay_seconds
        self.callback = callback


def test_keyring_vault_store_retrieve_delete() -> None:
    backend = FakeKeyring()
    vault = KeyringVault(backend)

    vault.store("reference", "sensitive-value")
    assert vault.retrieve("reference") == "sensitive-value"
    vault.delete("reference")
    assert vault.retrieve("reference") is None


def test_database_contains_reference_not_secret(tmp_path: Path) -> None:
    backend = FakeKeyring()
    service = SecretService(KeyringVault(backend))
    reference = service.create_reference(SecretType.ACCESS_TOKEN, "owner-1", "raw-value")
    database = Database(tmp_path / "data.db")
    try:
        run_migrations(database, MIGRATIONS)
        with database.unit_of_work() as unit:
            assert unit.session is not None
            unit.session.add(SecretMetadata.from_reference(reference))
            unit.commit()

        content = (tmp_path / "data.db").read_bytes()
        assert b"raw-value" not in content
        with database.engine.connect() as connection:
            row = connection.execute(
                text("SELECT secret_type, owner_id, vault_ref FROM secret_metadata")
            ).one()
        assert row == ("access_token", "owner-1", reference.vault_ref)
    finally:
        database.close()


def test_normal_metadata_export_excludes_secret() -> None:
    backend = FakeKeyring()
    service = SecretService(KeyringVault(backend))
    reference = service.create_reference(SecretType.PASSWORD, "owner-1", "raw-value")

    exported = json.dumps(service.export_metadata(reference))

    assert "raw-value" not in exported
    assert reference.vault_ref in exported


def test_explicit_encrypted_archive_round_trip() -> None:
    archive = encrypt_secret("raw-value", "operator-passphrase")
    serialized = archive.to_json()

    assert "raw-value" not in serialized
    assert "operator-passphrase" not in serialized
    assert decrypt_secret(EncryptedSecretArchive.from_json(serialized), "operator-passphrase") == (
        "raw-value"
    )


def test_temporary_reveal_only_clears_unchanged_clipboard() -> None:
    clipboard = FakeClipboard()
    scheduler = FakeScheduler()
    reveal_temporarily("raw-value", clipboard, scheduler, timeout_seconds=15)

    assert clipboard.text() == "raw-value"
    assert scheduler.delay == 15
    scheduler.callback()
    assert clipboard.text() == ""

    reveal_temporarily("raw-value", clipboard, scheduler)
    clipboard.set_text("operator-copy")
    scheduler.callback()
    assert clipboard.text() == "operator-copy"
