from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class BackupItem:
    name: str
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupManifest:
    backup_id: str
    version: str
    app_version: str
    created_at: datetime
    description: str
    includes_secrets: bool
    items: Sequence[BackupItem] = field(default_factory=tuple)
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "version": self.version,
            "app_version": self.app_version,
            "created_at": self.created_at.isoformat(),
            "description": self.description,
            "includes_secrets": self.includes_secrets,
            "checksum": self.checksum,
            "items": [
                {
                    "name": item.name,
                    "relative_path": item.relative_path,
                    "size_bytes": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in self.items
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupManifest":
        created_at = datetime.fromisoformat(data["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        items = tuple(
            BackupItem(
                name=it["name"],
                relative_path=it["relative_path"],
                size_bytes=int(it["size_bytes"]),
                sha256=it["sha256"],
            )
            for it in data.get("items", [])
        )
        return cls(
            backup_id=data["backup_id"],
            version=data.get("version", "1.0.0"),
            app_version=data.get("app_version", "1.0.0"),
            created_at=created_at,
            description=data.get("description", ""),
            includes_secrets=bool(data.get("includes_secrets", False)),
            items=items,
            checksum=data.get("checksum", ""),
        )


@dataclass(frozen=True, slots=True)
class RestorePreview:
    manifest: BackupManifest | None
    is_valid: bool
    validation_errors: Sequence[str] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    can_restore: bool = False
    requires_passphrase: bool = False


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    max_backups: int = 10
    max_age_days: int = 30
