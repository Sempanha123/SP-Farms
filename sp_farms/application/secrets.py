from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.secrets import SecretReference


class SecretRepository(Protocol):
    def list_by_owner_ids(
        self, owner_ids: Sequence[str] | None = None
    ) -> Sequence[SecretReference]: ...

    def save(self, reference: SecretReference) -> None: ...

    def delete(self, reference_id: str) -> None: ...
