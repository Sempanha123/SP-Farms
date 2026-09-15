import hashlib
import mimetypes
import shutil
from collections.abc import Callable, Sequence
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sp_farms.application.content_repository import ContentRepositoryPort
from sp_farms.application.ports import Clock
from sp_farms.application.unit_of_work import UnitOfWork
from sp_farms.domain.content import (
    CaptionTemplate,
    ContentItem,
    ContentStatus,
    HashtagSet,
    MediaAsset,
    MediaMetadata,
    MediaType,
)

if TYPE_CHECKING:
    pass

CHUNK_SIZE = 64 * 1024  # 64 KB


def compute_file_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_media_type(mime_type: str) -> MediaType:
    if mime_type.startswith("image/"):
        return MediaType.IMAGE
    elif mime_type.startswith("video/"):
        return MediaType.VIDEO
    elif mime_type.startswith("audio/"):
        return MediaType.AUDIO
    return MediaType.OTHER


def calculate_aspect_ratio(width: int | None, height: int | None) -> str | None:
    if not width or not height or width <= 0 or height <= 0:
        return None
    frac = Fraction(width, height).limit_denominator(20)
    # Recognize common standard aspect ratios
    ratio = width / height
    if abs(ratio - 16 / 9) < 0.05:
        return "16:9"
    elif abs(ratio - 9 / 16) < 0.05:
        return "9:16"
    elif abs(ratio - 1.0) < 0.02:
        return "1:1"
    elif abs(ratio - 4 / 5) < 0.05:
        return "4:5"
    elif abs(ratio - 4 / 3) < 0.05:
        return "4:3"
    return f"{frac.numerator}:{frac.denominator}"


def extract_media_dimensions(file_path: Path) -> tuple[int | None, int | None]:
    try:
        from PySide6.QtGui import QImageReader

        reader = QImageReader(str(file_path))
        if reader.canRead():
            size = reader.size()
            if size.isValid() and size.width() > 0 and size.height() > 0:
                return (size.width(), size.height())
    except Exception:
        pass
    return (None, None)


def generate_image_thumbnail(
    source_path: Path,
    target_path: Path,
    max_dimension: int = 256,
) -> bool:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage

        img = QImage(str(source_path))
        if not img.isNull():
            thumb = img.scaled(
                max_dimension,
                max_dimension,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            return bool(thumb.save(str(target_path), b"PNG"))
    except Exception:
        pass
    return False


class ContentService:
    def __init__(
        self,
        unit_of_work: Callable[[], UnitOfWork],
        content_repository_factory: Callable[[UnitOfWork], ContentRepositoryPort],
        clock: Clock,
        storage_dir: Path,
    ) -> None:
        self._uow = unit_of_work
        self._repo_factory = content_repository_factory
        self._clock = clock
        self._storage_dir = storage_dir
        self._assets_dir = storage_dir / "assets"
        self._thumbs_dir = storage_dir / "thumbnails"
        self._assets_dir.mkdir(parents=True, exist_ok=True)
        self._thumbs_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # Media Asset Operations
    # -------------------------------------------------------------------------

    def import_media(
        self,
        source_path: Path | str,
        folder: str = "default",
        tags: Sequence[str] = (),
        is_favorite: bool = False,
        allow_duplicate: bool = False,
    ) -> tuple[MediaAsset, bool]:
        """Import a file into the content library.

        Returns (MediaAsset, is_new). If allow_duplicate is False and hash matches,
        returns (existing_asset, False).
        """
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")

        file_size = source.stat().st_size
        sha256_hash = compute_file_sha256(source)

        with self._uow() as uow:
            repo = self._repo_factory(uow)
            existing = repo.get_asset_by_hash(sha256_hash)
            if existing is not None and not allow_duplicate:
                return (existing, False)

            # Determine mime and media type
            mime_type, _ = mimetypes.guess_type(str(source))
            if not mime_type:
                mime_type = "application/octet-stream"
            media_type = detect_media_type(mime_type)

            asset_id = str(uuid4())
            extension = source.suffix.lower()
            dest_filename = f"{asset_id}{extension}"
            dest_path = self._assets_dir / dest_filename
            shutil.copy2(source, dest_path)

            # Metadata extraction
            width, height = extract_media_dimensions(dest_path)
            aspect_ratio = calculate_aspect_ratio(width, height)
            duration_seconds = None

            # Thumbnail generation
            thumb_rel_path: str | None = None
            if media_type == MediaType.IMAGE:
                thumb_dest = self._thumbs_dir / f"{asset_id}.png"
                if generate_image_thumbnail(dest_path, thumb_dest):
                    thumb_rel_path = str(thumb_dest)

            metadata = MediaMetadata(
                mime_type=mime_type,
                file_size_bytes=file_size,
                sha256_hash=sha256_hash,
                width=width,
                height=height,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
            )

            asset = MediaAsset(
                id=asset_id,
                file_path=str(dest_path),
                file_name=source.name,
                media_type=media_type,
                metadata=metadata,
                thumbnail_path=thumb_rel_path,
                folder=folder or "default",
                tags=tuple(sorted(set(tags))),
                is_favorite=is_favorite,
                is_archived=False,
                created_at=self._clock.now(),
                updated_at=self._clock.now(),
            )

            repo.add_asset(asset)
            uow.commit()
            return (asset, True)

    def get_asset(self, asset_id: str) -> MediaAsset | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get_asset(asset_id)

    def list_assets(
        self,
        folder: str | None = None,
        media_type: MediaType | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = False,
        tag: str | None = None,
        search_query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[MediaAsset]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_assets(
                folder=folder,
                media_type=media_type,
                is_favorite=is_favorite,
                is_archived=is_archived,
                tag=tag,
                search_query=search_query,
                limit=limit,
                offset=offset,
            )

    def update_asset(
        self,
        asset_id: str,
        folder: str | None = None,
        tags: Sequence[str] | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = None,
    ) -> MediaAsset | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            asset = repo.get_asset(asset_id)
            if asset is None:
                return None
            updated = asset.with_updates(
                folder=folder,
                tags=tags,
                is_favorite=is_favorite,
                is_archived=is_archived,
            )
            repo.update_asset(updated)
            uow.commit()
            return updated

    def toggle_asset_favorite(self, asset_id: str) -> MediaAsset | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            asset = repo.get_asset(asset_id)
            if asset is None:
                return None
            updated = asset.with_updates(is_favorite=not asset.is_favorite)
            repo.update_asset(updated)
            uow.commit()
            return updated

    def archive_asset(self, asset_id: str) -> MediaAsset | None:
        return self.update_asset(asset_id, is_archived=True)

    def unarchive_asset(self, asset_id: str) -> MediaAsset | None:
        return self.update_asset(asset_id, is_archived=False)

    def delete_asset(self, asset_id: str, remove_files: bool = True) -> bool:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            asset = repo.get_asset(asset_id)
            if asset is None:
                return False
            success = repo.delete_asset(asset_id)
            if success:
                uow.commit()
                if remove_files:
                    try:
                        p = Path(asset.file_path)
                        if p.exists():
                            p.unlink()
                        if asset.thumbnail_path:
                            tp = Path(asset.thumbnail_path)
                            if tp.exists():
                                tp.unlink()
                    except Exception:
                        pass
                return True
            return False

    def list_folders(self) -> Sequence[str]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_folders()

    # -------------------------------------------------------------------------
    # Caption Template Operations
    # -------------------------------------------------------------------------

    def create_caption_template(
        self,
        name: str,
        content: str,
        variables: Sequence[str] = (),
        tags: Sequence[str] = (),
        is_favorite: bool = False,
    ) -> CaptionTemplate:
        template = CaptionTemplate.create(
            name=name,
            content=content,
            variables=variables,
            tags=tags,
            is_favorite=is_favorite,
        )
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            repo.add_caption_template(template)
            uow.commit()
        return template

    def get_caption_template(self, template_id: str) -> CaptionTemplate | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get_caption_template(template_id)

    def list_caption_templates(
        self,
        is_favorite: bool | None = None,
        tag: str | None = None,
        search_query: str | None = None,
    ) -> Sequence[CaptionTemplate]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_caption_templates(
                is_favorite=is_favorite,
                tag=tag,
                search_query=search_query,
            )

    def delete_caption_template(self, template_id: str) -> bool:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            res = repo.delete_caption_template(template_id)
            if res:
                uow.commit()
            return res

    # -------------------------------------------------------------------------
    # Hashtag Set Operations
    # -------------------------------------------------------------------------

    def create_hashtag_set(
        self,
        name: str,
        hashtags: Sequence[str],
        category: str = "general",
        is_favorite: bool = False,
    ) -> HashtagSet:
        set_obj = HashtagSet.create(
            name=name,
            hashtags=hashtags,
            category=category,
            is_favorite=is_favorite,
        )
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            repo.add_hashtag_set(set_obj)
            uow.commit()
        return set_obj

    def get_hashtag_set(self, set_id: str) -> HashtagSet | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get_hashtag_set(set_id)

    def list_hashtag_sets(
        self,
        category: str | None = None,
        is_favorite: bool | None = None,
        search_query: str | None = None,
    ) -> Sequence[HashtagSet]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_hashtag_sets(
                category=category,
                is_favorite=is_favorite,
                search_query=search_query,
            )

    def delete_hashtag_set(self, set_id: str) -> bool:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            res = repo.delete_hashtag_set(set_id)
            if res:
                uow.commit()
            return res

    # -------------------------------------------------------------------------
    # Content Item Operations
    # -------------------------------------------------------------------------

    def create_content_item(
        self,
        title: str,
        body: str = "",
        media_asset_ids: Sequence[str] = (),
        hashtag_set_ids: Sequence[str] = (),
        caption_template_id: str | None = None,
        status: ContentStatus = ContentStatus.DRAFT,
        folder: str = "default",
        tags: Sequence[str] = (),
        is_favorite: bool = False,
    ) -> ContentItem:
        item = ContentItem.create(
            title=title,
            body=body,
            media_asset_ids=media_asset_ids,
            hashtag_set_ids=hashtag_set_ids,
            caption_template_id=caption_template_id,
            status=status,
            folder=folder,
            tags=tags,
            is_favorite=is_favorite,
        )
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            repo.add_content_item(item)
            uow.commit()
        return item

    def get_content_item(self, item_id: str) -> ContentItem | None:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.get_content_item(item_id)

    def list_content_items(
        self,
        folder: str | None = None,
        status: str | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = False,
        search_query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ContentItem]:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            return repo.list_content_items(
                folder=folder,
                status=status,
                is_favorite=is_favorite,
                is_archived=is_archived,
                search_query=search_query,
                limit=limit,
                offset=offset,
            )

    def delete_content_item(self, item_id: str) -> bool:
        with self._uow() as uow:
            repo = self._repo_factory(uow)
            res = repo.delete_content_item(item_id)
            if res:
                uow.commit()
            return res
