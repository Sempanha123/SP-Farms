from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sp_farms.application.vault import Vault
from sp_farms.domain.secrets import SecretReference, SecretType


class SecretService:
    def __init__(self, vault: Vault) -> None:
        self._vault = vault

    def create_reference(
        self,
        secret_type: SecretType,
        owner_id: str,
        value: str,
    ) -> SecretReference:
        now = datetime.now(UTC)
        reference = SecretReference(
            id=str(uuid4()),
            secret_type=secret_type,
            owner_id=owner_id,
            vault_ref=str(uuid4()),
            created_at=now,
            updated_at=now,
        )
        self._vault.store(reference.vault_ref, value)
        return reference

    def reveal(self, reference: SecretReference) -> str | None:
        return self._vault.retrieve(reference.vault_ref)

    def delete(self, reference: SecretReference) -> None:
        self._vault.delete(reference.vault_ref)

    @staticmethod
    def export_metadata(reference: SecretReference) -> dict[str, Any]:
        metadata = asdict(reference)
        metadata["secret_type"] = reference.secret_type.value
        metadata["created_at"] = reference.created_at.isoformat()
        metadata["updated_at"] = reference.updated_at.isoformat()
        return metadata
