from collections.abc import Sequence
from typing import Protocol

from sp_farms.domain.content import (
    CaptionTemplate,
    ContentItem,
    HashtagSet,
    MediaAsset,
    MediaType,
)


class ContentRepositoryPort(Protocol):
    # Media Assets
    def add_asset(self, asset: MediaAsset) -> None: ...

    def update_asset(self, asset: MediaAsset) -> None: ...

    def get_asset(self, asset_id: str) -> MediaAsset | None: ...

    def get_asset_by_hash(self, sha256_hash: str) -> MediaAsset | None: ...

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
    ) -> Sequence[MediaAsset]: ...

    def delete_asset(self, asset_id: str) -> bool: ...

    def count_assets(
        self,
        folder: str | None = None,
        is_archived: bool | None = False,
    ) -> int: ...

    def list_folders(self) -> Sequence[str]: ...

    # Caption Templates
    def add_caption_template(self, template: CaptionTemplate) -> None: ...

    def update_caption_template(self, template: CaptionTemplate) -> None: ...

    def get_caption_template(self, template_id: str) -> CaptionTemplate | None: ...

    def list_caption_templates(
        self,
        is_favorite: bool | None = None,
        tag: str | None = None,
        search_query: str | None = None,
    ) -> Sequence[CaptionTemplate]: ...

    def delete_caption_template(self, template_id: str) -> bool: ...

    # Hashtag Sets
    def add_hashtag_set(self, hashtag_set: HashtagSet) -> None: ...

    def update_hashtag_set(self, hashtag_set: HashtagSet) -> None: ...

    def get_hashtag_set(self, set_id: str) -> HashtagSet | None: ...

    def list_hashtag_sets(
        self,
        category: str | None = None,
        is_favorite: bool | None = None,
        search_query: str | None = None,
    ) -> Sequence[HashtagSet]: ...

    def delete_hashtag_set(self, set_id: str) -> bool: ...

    # Content Items
    def add_content_item(self, item: ContentItem) -> None: ...

    def update_content_item(self, item: ContentItem) -> None: ...

    def get_content_item(self, item_id: str) -> ContentItem | None: ...

    def list_content_items(
        self,
        folder: str | None = None,
        status: str | None = None,
        is_favorite: bool | None = None,
        is_archived: bool | None = False,
        search_query: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[ContentItem]: ...

    def delete_content_item(self, item_id: str) -> bool: ...
