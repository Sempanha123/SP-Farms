from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from sp_farms.domain.device_pool import (
    AccountWorkspaceLock,
    DevicePoolPolicy,
    SnapshotMetadataRecord,
)


class DevicePoolRepository(Protocol):
    def acquire_lock(
        self,
        account_id: str,
        device_key: str,
        job_id: str | None,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> AccountWorkspaceLock | None: ...

    def get_lock_by_account(self, account_id: str) -> AccountWorkspaceLock | None: ...

    def get_lock_by_device(self, device_key: str) -> AccountWorkspaceLock | None: ...

    def list_active_locks(self, now: datetime) -> Sequence[AccountWorkspaceLock]: ...

    def release_lock(self, account_id: str) -> bool: ...

    def release_stale_locks(self, now: datetime) -> int: ...

    def refresh_lock(
        self,
        account_id: str,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> bool: ...

    def save_snapshot_record(self, record: SnapshotMetadataRecord) -> None: ...

    def get_snapshot_record(self, snapshot_id: str) -> SnapshotMetadataRecord | None: ...

    def list_snapshots_for_account(
        self, account_id: str
    ) -> Sequence[SnapshotMetadataRecord]: ...

    def list_all_snapshots(self) -> Sequence[SnapshotMetadataRecord]: ...

    def delete_snapshot_record(self, snapshot_id: str) -> bool: ...

    def update_snapshot_last_restored(
        self, snapshot_id: str, restored_at: datetime
    ) -> None: ...

    def get_policy(self, name: str) -> DevicePoolPolicy | None: ...

    def get_active_policy(self) -> DevicePoolPolicy | None: ...

    def save_policy(self, policy: DevicePoolPolicy) -> None: ...

