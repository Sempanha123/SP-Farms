"""Domain entities and value objects for social media post analytics and engagement metrics."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from sp_farms.domain.composer import PostType


class AnalyticsTimeRange(StrEnum):
    LAST_24_HOURS = "24h"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    ALL_TIME = "all"


@dataclass(frozen=True, slots=True)
class PostAnalyticsSnapshot:
    """Point-in-time metrics snapshot for a published Facebook post, reel, or story."""

    id: str
    external_post_id: str
    account_id: str
    destination_id: str
    destination_name: str
    post_type: PostType
    publish_attempt_id: str | None = None
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    views_count: int = 0
    impressions_count: int = 0
    reach_count: int = 0
    synced_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_interactions(self) -> int:
        return self.likes_count + self.comments_count + self.shares_count

    @property
    def engagement_rate(self) -> float:
        """Calculates engagement rate based on reach or impressions."""
        denominator = self.reach_count or self.impressions_count
        if denominator <= 0:
            return 0.0
        return round((self.total_interactions / denominator) * 100.0, 2)


@dataclass(frozen=True, slots=True)
class AggregatedMetrics:
    """Aggregated engagement metrics across multiple posts or time windows."""

    total_posts: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_views: int = 0
    total_impressions: int = 0
    total_reach: int = 0

    @property
    def total_interactions(self) -> int:
        return self.total_likes + self.total_comments + self.total_shares

    @property
    def average_engagement_rate(self) -> float:
        denominator = self.total_reach or self.total_impressions
        if denominator <= 0:
            return 0.0
        return round((self.total_interactions / denominator) * 100.0, 2)
