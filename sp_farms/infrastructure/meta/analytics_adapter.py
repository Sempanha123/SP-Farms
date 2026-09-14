"""Adapter for fetching post engagement and reach metrics from Meta Graph API."""

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from sp_farms.application.analytics_port import AnalyticsPort
from sp_farms.domain.meta import MetaApiError, MetaOAuthConfig
from sp_farms.infrastructure.logging import get_logger

logger = get_logger("meta.analytics")


class MetaAnalyticsAdapter(AnalyticsPort):
    """Fetches insights and reactions from Meta Graph API."""

    def __init__(
        self,
        config: MetaOAuthConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config or MetaOAuthConfig(client_id="default", client_secret="secret", redirect_uri="")
        self._client = http_client or httpx.Client(timeout=30.0)

    def fetch_post_metrics(
        self,
        external_post_id: str,
        access_token: str,
    ) -> Mapping[str, int]:
        """Fetch likes, comments, shares, views, and reach using Graph API post insights."""
        url = f"{self._config.base_url}/{self._config.graph_version}/{external_post_id}"
        params = {
            "fields": "likes.summary(true),comments.summary(true),shares,insights.metric(post_impressions,post_impressions_unique,post_video_views)",
            "access_token": access_token,
        }

        try:
            resp = self._client.get(url, params=params)
            if resp.status_code != 200:
                logger.warning("Graph API returned %d for post %s metrics", resp.status_code, external_post_id)
                return self._parse_fallback_response(resp.json() if resp.content else {})
            data = resp.json()
            return self._parse_metrics_payload(data)
        except Exception as e:
            logger.error("Failed fetching metrics from Graph API for %s: %s", external_post_id, e)
            raise MetaApiError(f"Analytics query failed: {e}") from e

    def _parse_metrics_payload(self, data: dict[str, Any]) -> dict[str, int]:
        likes = data.get("likes", {}).get("summary", {}).get("total_count", 0)
        comments = data.get("comments", {}).get("summary", {}).get("total_count", 0)
        shares = data.get("shares", {}).get("count", 0)

        impressions = 0
        reach = 0
        views = 0

        insights = data.get("insights", {}).get("data", [])
        for item in insights:
            name = item.get("name")
            values = item.get("values", [])
            val = values[0].get("value", 0) if values else 0
            if name == "post_impressions":
                impressions = int(val)
            elif name == "post_impressions_unique":
                reach = int(val)
            elif name == "post_video_views":
                views = int(val)

        return {
            "likes_count": int(likes),
            "comments_count": int(comments),
            "shares_count": int(shares),
            "views_count": int(views),
            "impressions_count": int(impressions),
            "reach_count": int(reach),
        }

    def _parse_fallback_response(self, data: dict[str, Any]) -> dict[str, int]:
        return {
            "likes_count": 0,
            "comments_count": 0,
            "shares_count": 0,
            "views_count": 0,
            "impressions_count": 0,
            "reach_count": 0,
        }


class FakeAnalyticsAdapter(AnalyticsPort):
    """Deterministic in-memory analytics adapter for tests."""

    def __init__(self) -> None:
        self.metrics_db: dict[str, dict[str, int]] = {}

    def set_metrics(
        self,
        external_post_id: str,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        views: int = 0,
        impressions: int = 0,
        reach: int = 0,
    ) -> None:
        self.metrics_db[external_post_id] = {
            "likes_count": likes,
            "comments_count": comments,
            "shares_count": shares,
            "views_count": views,
            "impressions_count": impressions,
            "reach_count": reach,
        }

    def fetch_post_metrics(
        self,
        external_post_id: str,
        access_token: str,
    ) -> Mapping[str, int]:
        if external_post_id in self.metrics_db:
            return self.metrics_db[external_post_id]
        return {
            "likes_count": 42,
            "comments_count": 8,
            "shares_count": 3,
            "views_count": 120,
            "impressions_count": 550,
            "reach_count": 410,
        }
