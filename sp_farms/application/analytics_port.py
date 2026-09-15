"""Protocols for fetching social engagement metrics from Meta Graph API or mobile interfaces."""

from collections.abc import Mapping
from typing import Protocol


class AnalyticsPort(Protocol):
    """Port for querying engagement statistics for posts, reels, and videos."""

    def fetch_post_metrics(
        self,
        external_post_id: str,
        access_token: str,
    ) -> Mapping[str, int]:
        """Fetch likes, comments, shares, views, impressions, reach for a post."""
        ...
