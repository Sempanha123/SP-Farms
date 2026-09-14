from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MediaType(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    OTHER = "OTHER"


class ContentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    mime_type: str
    file_size_bytes: int
    sha256_hash: str
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    aspect_ratio: str | None = None

    @property
    def formatted_size(self) -> str:
        size = self.file_size_bytes
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    @property
    def resolution_label(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return "—"


@dataclass(frozen=True, slots=True)
class MediaAsset:
    id: str
    file_path: str
    file_name: str
    media_type: MediaType
    metadata: MediaMetadata
    thumbnail_path: str | None = None
    folder: str = "default"
    tags: tuple[str, ...] = field(default_factory=tuple)
    is_favorite: bool = False
    is_archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        file_path: str,
        file_name: str,
        media_type: MediaType,
        metadata: MediaMetadata,
        thumbnail_path: str | None = None,
        folder: str = "default",
        tags: Sequence[str] = (),
        is_favorite: bool = False,
        is_archived: bool = False,
        asset_id: str | None = None,
    ) -> "MediaAsset":
        now = datetime.now(UTC)
        return cls(
            id=asset_id or str(uuid4()),
            file_path=file_path,
            file_name=file_name,
            media_type=media_type,
            metadata=metadata,
            thumbnail_path=thumbnail_path,
            folder=folder or "default",
            tags=tuple(sorted(set(tags))),
            is_favorite=is_favorite,
            is_archived=is_archived,
            created_at=now,
            updated_at=now,
        )

    def with_updates(
        self,
        folder: str | None = None,
        tags: Sequence[str] | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
        thumbnail_path: str | None = None,
    ) -> "MediaAsset":
        return MediaAsset(
            id=self.id,
            file_path=self.file_path,
            file_name=self.file_name,
            media_type=self.media_type,
            metadata=self.metadata,
            thumbnail_path=self.thumbnail_path if thumbnail_path is None else thumbnail_path,
            folder=self.folder if folder is None else folder,
            tags=self.tags if tags is None else tuple(sorted(set(tags))),
            is_favorite=self.is_favorite if is_favorite is None else is_favorite,
            is_archived=self.is_archived if is_archived is None else is_archived,
            created_at=self.created_at,
            updated_at=datetime.now(UTC),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "media_type": self.media_type.value,
            "thumbnail_path": self.thumbnail_path,
            "folder": self.folder,
            "tags": list(self.tags),
            "is_favorite": self.is_favorite,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": {
                "mime_type": self.metadata.mime_type,
                "file_size_bytes": self.metadata.file_size_bytes,
                "sha256_hash": self.metadata.sha256_hash,
                "width": self.metadata.width,
                "height": self.metadata.height,
                "duration_seconds": self.metadata.duration_seconds,
                "aspect_ratio": self.metadata.aspect_ratio,
            },
        }


@dataclass(frozen=True, slots=True)
class CaptionTemplate:
    id: str
    name: str
    content: str
    variables: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    is_favorite: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        content: str,
        variables: Sequence[str] = (),
        tags: Sequence[str] = (),
        is_favorite: bool = False,
        template_id: str | None = None,
    ) -> "CaptionTemplate":
        now = datetime.now(UTC)
        return cls(
            id=template_id or str(uuid4()),
            name=name,
            content=content,
            variables=tuple(variables),
            tags=tuple(sorted(set(tags))),
            is_favorite=is_favorite,
            created_at=now,
            updated_at=now,
        )

    def render(self, values: dict[str, str]) -> str:
        rendered = self.content
        for var in self.variables:
            placeholder = f"{{{var}}}"
            if placeholder in rendered:
                rendered = rendered.replace(placeholder, values.get(var, f"{{{var}}}"))
        return rendered

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "content": self.content,
            "variables": list(self.variables),
            "tags": list(self.tags),
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class HashtagSet:
    id: str
    name: str
    hashtags: tuple[str, ...] = field(default_factory=tuple)
    category: str = "general"
    is_favorite: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        hashtags: Sequence[str],
        category: str = "general",
        is_favorite: bool = False,
        set_id: str | None = None,
    ) -> "HashtagSet":
        clean_tags: list[str] = []
        for t in hashtags:
            cleaned = t.strip()
            if not cleaned:
                continue
            if not cleaned.startswith("#"):
                cleaned = f"#{cleaned}"
            if cleaned not in clean_tags:
                clean_tags.append(cleaned)

        now = datetime.now(UTC)
        return cls(
            id=set_id or str(uuid4()),
            name=name,
            hashtags=tuple(clean_tags),
            category=category or "general",
            is_favorite=is_favorite,
            created_at=now,
            updated_at=now,
        )

    def formatted_string(self) -> str:
        return " ".join(self.hashtags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "hashtags": list(self.hashtags),
            "category": self.category,
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ContentItem:
    id: str
    title: str
    body: str
    media_asset_ids: tuple[str, ...] = field(default_factory=tuple)
    hashtag_set_ids: tuple[str, ...] = field(default_factory=tuple)
    caption_template_id: str | None = None
    status: ContentStatus = ContentStatus.DRAFT
    folder: str = "default"
    tags: tuple[str, ...] = field(default_factory=tuple)
    is_favorite: bool = False
    is_archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        title: str,
        body: str = "",
        media_asset_ids: Sequence[str] = (),
        hashtag_set_ids: Sequence[str] = (),
        caption_template_id: str | None = None,
        status: ContentStatus = ContentStatus.DRAFT,
        folder: str = "default",
        tags: Sequence[str] = (),
        is_favorite: bool = False,
        is_archived: bool = False,
        item_id: str | None = None,
    ) -> "ContentItem":
        now = datetime.now(UTC)
        return cls(
            id=item_id or str(uuid4()),
            title=title,
            body=body,
            media_asset_ids=tuple(media_asset_ids),
            hashtag_set_ids=tuple(hashtag_set_ids),
            caption_template_id=caption_template_id,
            status=status,
            folder=folder or "default",
            tags=tuple(sorted(set(tags))),
            is_favorite=is_favorite,
            is_archived=is_archived,
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "media_asset_ids": list(self.media_asset_ids),
            "hashtag_set_ids": list(self.hashtag_set_ids),
            "caption_template_id": self.caption_template_id,
            "status": self.status.value,
            "folder": self.folder,
            "tags": list(self.tags),
            "is_favorite": self.is_favorite,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
