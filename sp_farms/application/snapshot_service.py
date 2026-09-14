import hashlib
import json
import zipfile
from collections.abc import Callable, Sequence
from contextlib import suppress
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sp_farms.application.accounts import AccountRepository
from sp_farms.application.device_pool import DevicePoolRepository
from sp_farms.application.device_profiles import DeviceProfileRepository
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.device_pool import (
    AccountWorkspaceSnapshot,
    SnapshotMetadataRecord,
)

if TYPE_CHECKING:
    pass


SCHEMA_VERSION = "1.0"
DEFAULT_MAX_SNAPSHOT_SIZE = 5 * 1024 * 1024  # 5 MB limit for lightweight snapshots


class SnapshotService:
    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        pool_repo_factory: Callable[[UnitOfWork], DevicePoolRepository],
        account_repo_factory: Callable[[UnitOfWork], AccountRepository],
        device_profile_repo_factory: Callable[[UnitOfWork], DeviceProfileRepository],
        storage_dir: Path,
        clock: Clock,
        max_size_bytes: int = DEFAULT_MAX_SNAPSHOT_SIZE,
    ) -> None:
        self._unit_of_work = unit_of_work_factory
        self._pool_repo = pool_repo_factory
        self._account_repo = account_repo_factory
        self._profile_repo = device_profile_repo_factory
        self._storage_dir = storage_dir
        self._clock = clock
        self._max_size_bytes = max_size_bytes
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(
        self,
        account_id: str,
        notes: str = "",
    ) -> SnapshotMetadataRecord:
        now = self._clock.now()
        with self._unit_of_work() as uow:
            account = self._account_repo(uow).get_account(account_id)
            if account is None:
                raise ValueError(f"Account {account_id} not found")

            binding = self._profile_repo(uow).get_binding(account_id)
            device_profile_id = binding.device_profile_id if binding else None
            device_prefs: dict[str, Any] = {}
            if device_profile_id:
                prof = self._profile_repo(uow).get_by_id(device_profile_id)
                if prof:
                    device_prefs = {
                        "device_model": prof.model,
                        "resolution": prof.resolution,
                        "dpi": prof.dpi,
                        "locale": prof.locale,
                        "timezone": prof.timezone,
                    }

            email_masked = ""
            if account.primary_email:
                parts = account.primary_email.split("@")
                if len(parts) == 2 and len(parts[0]) > 2:
                    email_masked = f"{parts[0][:2]}***@{parts[1]}"
                else:
                    email_masked = "***@***"

            phone_masked = ""
            if account.phone:
                phone_masked = f"***{account.phone[-4:]}" if len(account.phone) >= 4 else "***"

            snapshot_id = str(uuid4())
            snapshot_obj = AccountWorkspaceSnapshot(
                id=snapshot_id,
                account_id=account.id,
                display_name=account.display_name,
                platform_uid=account.platform_uid or "",
                primary_email_masked=email_masked,
                phone_masked=phone_masked,
                preferred_app=account.preferred_app.value,
                locale=account.locale or "en_US",
                timezone=account.timezone or "UTC",
                schema_version=SCHEMA_VERSION,
                created_at=now,
                device_profile_id=device_profile_id,
                device_preferences=device_prefs,
                qa_profile_ref=None,
                vault_secret_refs=[f"vault://account/{account.id}/credentials"]
                if account.platform_uid
                else [],
                categories=[account.category_id] if account.category_id else [],
                tags=list(account.tag_ids),
                notes=notes,
            )

            # Serialize payload to JSON and compress into .spws (zip) archive
            payload_dict = {
                "id": snapshot_obj.id,
                "account_id": snapshot_obj.account_id,
                "display_name": snapshot_obj.display_name,
                "platform_uid": snapshot_obj.platform_uid,
                "primary_email_masked": snapshot_obj.primary_email_masked,
                "phone_masked": snapshot_obj.phone_masked,
                "preferred_app": snapshot_obj.preferred_app,
                "locale": snapshot_obj.locale,
                "timezone": snapshot_obj.timezone,
                "schema_version": snapshot_obj.schema_version,
                "created_at": snapshot_obj.created_at.isoformat(),
                "device_profile_id": snapshot_obj.device_profile_id,
                "device_preferences": snapshot_obj.device_preferences,
                "qa_profile_ref": snapshot_obj.qa_profile_ref,
                "vault_secret_refs": snapshot_obj.vault_secret_refs,
                "categories": snapshot_obj.categories,
                "tags": snapshot_obj.tags,
                "notes": snapshot_obj.notes,
            }

            raw_bytes = json.dumps(payload_dict, indent=2).encode("utf-8")
            checksum = hashlib.sha256(raw_bytes).hexdigest()

            # Store in archive
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json", raw_bytes)

            archive_bytes = zip_buffer.getvalue()
            size_bytes = len(archive_bytes)

            if size_bytes > self._max_size_bytes:
                raise ValueError(
                    f"Snapshot size {size_bytes} exceeds configured maximum of "
                    f"{self._max_size_bytes} bytes"
                )

            # Write file: backups/accounts/<account_uuid>/<timestamp>.spws
            acct_dir = self._storage_dir / "accounts" / account_id
            acct_dir.mkdir(parents=True, exist_ok=True)
            stamp_str = now.strftime("%Y%m%d_%H%M%S")
            file_path = acct_dir / f"{stamp_str}_{snapshot_id[:8]}.spws"
            file_path.write_bytes(archive_bytes)

            record = SnapshotMetadataRecord(
                id=snapshot_id,
                account_id=account.id,
                path=str(file_path),
                size_bytes=size_bytes,
                schema_version=SCHEMA_VERSION,
                checksum=checksum,
                device_profile_id=device_profile_id,
                preferred_app=account.preferred_app.value,
                notes=notes,
                created_at=now,
                last_restored_at=None,
            )

            self._pool_repo(uow).save_snapshot_record(record)
            uow.commit()
            return record

    def get_snapshot_record(self, snapshot_id: str) -> SnapshotMetadataRecord | None:
        with self._unit_of_work() as uow:
            return self._pool_repo(uow).get_snapshot_record(snapshot_id)

    def list_snapshots_for_account(
        self, account_id: str
    ) -> Sequence[SnapshotMetadataRecord]:
        with self._unit_of_work() as uow:
            return self._pool_repo(uow).list_snapshots_for_account(account_id)

    def list_all_snapshots(self) -> Sequence[SnapshotMetadataRecord]:
        with self._unit_of_work() as uow:
            return self._pool_repo(uow).list_all_snapshots()

    def read_snapshot_payload(self, snapshot_id: str) -> dict[str, Any]:
        with self._unit_of_work() as uow:
            record = self._pool_repo(uow).get_snapshot_record(snapshot_id)
        if record is None:
            raise FileNotFoundError(f"Snapshot record {snapshot_id} not found")

        path = Path(record.path)
        if not path.exists():
            raise FileNotFoundError(f"Snapshot file {path} not found on disk")

        with zipfile.ZipFile(path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError(f"Invalid snapshot archive {path}: missing manifest.json")
            manifest_bytes = zf.read("manifest.json")

        actual_checksum = hashlib.sha256(manifest_bytes).hexdigest()
        if actual_checksum != record.checksum:
            raise ValueError(
                f"Checksum mismatch for snapshot {snapshot_id}: "
                f"expected {record.checksum}, got {actual_checksum}"
            )

        data = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Invalid snapshot payload: root must be a dict")
        return data

    def verify_snapshot(self, snapshot_id: str) -> bool:
        try:
            self.read_snapshot_payload(snapshot_id)
            return True
        except Exception:
            return False

    def export_snapshot(self, snapshot_id: str, destination: Path) -> Path:
        with self._unit_of_work() as uow:
            record = self._pool_repo(uow).get_snapshot_record(snapshot_id)
        if record is None:
            raise FileNotFoundError(f"Snapshot record {snapshot_id} not found")
        src_path = Path(record.path)
        if not src_path.exists():
            raise FileNotFoundError(f"Snapshot file {src_path} not found on disk")

        destination.parent.mkdir(parents=True, exist_ok=True)
        target = destination / src_path.name if destination.is_dir() else destination
        target.write_bytes(src_path.read_bytes())
        return target

    def import_snapshot(
        self, file_path: Path, account_id: str | None = None
    ) -> SnapshotMetadataRecord:
        if not file_path.exists():
            raise FileNotFoundError(f"Snapshot file {file_path} not found")

        with zipfile.ZipFile(file_path, "r") as zf:
            if "manifest.json" not in zf.namelist():
                raise ValueError(f"Invalid snapshot archive {file_path}: missing manifest.json")
            manifest_bytes = zf.read("manifest.json")

        checksum = hashlib.sha256(manifest_bytes).hexdigest()
        data = json.loads(manifest_bytes.decode("utf-8"))
        target_account_id = account_id or data.get("account_id")
        if not target_account_id:
            raise ValueError("No account_id specified in snapshot or argument")

        now = self._clock.now()
        snapshot_id = str(uuid4())
        acct_dir = self._storage_dir / "accounts" / target_account_id
        acct_dir.mkdir(parents=True, exist_ok=True)
        stamp_str = now.strftime("%Y%m%d_%H%M%S")
        dest_path = acct_dir / f"{stamp_str}_{snapshot_id[:8]}.spws"
        dest_path.write_bytes(file_path.read_bytes())

        size_bytes = dest_path.stat().st_size
        record = SnapshotMetadataRecord(
            id=snapshot_id,
            account_id=target_account_id,
            path=str(dest_path),
            size_bytes=size_bytes,
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            checksum=checksum,
            device_profile_id=data.get("device_profile_id"),
            preferred_app=data.get("preferred_app", "browser"),
            notes=data.get("notes", ""),
            created_at=now,
            last_restored_at=None,
        )
        with self._unit_of_work() as uow:
            self._pool_repo(uow).save_snapshot_record(record)
            uow.commit()
        return record

    def delete_snapshot(self, snapshot_id: str) -> bool:
        with self._unit_of_work() as uow:
            record = self._pool_repo(uow).get_snapshot_record(snapshot_id)
            if record is not None:
                path = Path(record.path)
                if path.exists():
                    with suppress(OSError):
                        path.unlink()
                res = self._pool_repo(uow).delete_snapshot_record(snapshot_id)
                uow.commit()
                return res
        return False
