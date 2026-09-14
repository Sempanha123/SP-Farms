"""Protocols for official Meta Graph API publishing."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PublishResponse:
    """Result returned by publishing adapters upon successful creation."""

    id: str
    post_id: str | None = None
    media_id: str | None = None
    raw_response: Mapping[str, Any] | None = None


class PublishingPort(Protocol):
    """Port interface for executing content publication to official destinations."""

    def publish_page_feed(
        self,
        page_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
        published: bool = True,
    ) -> PublishResponse:
        """Publish a text/link post to a Facebook Page."""
        ...

    def publish_page_photo(
        self,
        page_id: str,
        access_token: str,
        caption: str,
        photo_url: str | None = None,
        photo_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        """Publish a photo post to a Facebook Page."""
        ...

    def publish_page_video(
        self,
        page_id: str,
        access_token: str,
        description: str,
        title: str | None = None,
        video_url: str | None = None,
        video_bytes: bytes | None = None,
        published: bool = True,
    ) -> PublishResponse:
        """Publish a video post or reel to a Facebook Page."""
        ...

    def publish_group_feed(
        self,
        group_id: str,
        access_token: str,
        message: str,
        link: str | None = None,
    ) -> PublishResponse:
        """Publish a text or link post to an authorized Facebook Group."""
        ...
