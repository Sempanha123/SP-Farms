"""Update service abstraction and semantic version comparison."""

import re
from collections.abc import Mapping
from typing import Any, Protocol

from sp_farms.domain.health import AppVersionInfo


def parse_semver(version_str: str) -> tuple[int, int, int, str]:
    """Parse semver string into (major, minor, patch, pre_release)."""
    clean = version_str.strip().lstrip("vV")
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$"
    match = re.match(pattern, clean)
    if not match:
        # Fallback for simple single/double digit versions
        parts = clean.split(".")
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch, "")
        except ValueError:
            return (0, 0, 0, clean)

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    prerelease = match.group(4) or ""
    return (major, minor, patch, prerelease)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two version strings.

    Returns:
        1 if v1 > v2
       -1 if v1 < v2
        0 if v1 == v2
    """
    maj1, min1, pat1, pre1 = parse_semver(v1)
    maj2, min2, pat2, pre2 = parse_semver(v2)

    if (maj1, min1, pat1) > (maj2, min2, pat2):
        return 1
    if (maj1, min1, pat1) < (maj2, min2, pat2):
        return -1

    # Numeric parts equal, check prerelease
    # A version without prerelease is newer than one with prerelease (e.g. 1.0.0 > 1.0.0-beta)
    if not pre1 and pre2:
        return 1
    if pre1 and not pre2:
        return -1
    if pre1 < pre2:
        return -1
    if pre1 > pre2:
        return 1
    return 0


def is_newer_version(candidate: str, current: str) -> bool:
    """Return True if candidate is strictly newer than current."""
    return compare_versions(candidate, current) > 0


class UpdatePort(Protocol):
    def fetch_latest_release(self, channel: str = "stable") -> Mapping[str, Any]: ...


class FakeUpdateAdapter:
    """Offline/in-memory update adapter for testing and airgapped environments."""

    def __init__(
        self,
        latest_version: str = "1.0.0",
        release_notes: str = "Initial production release",
        download_url: str = "https://github.com/Sempanha123/SP-Farms/releases",
    ) -> None:
        self.latest_version = latest_version
        self.release_notes = release_notes
        self.download_url = download_url

    def fetch_latest_release(self, channel: str = "stable") -> Mapping[str, Any]:
        return {
            "version": self.latest_version,
            "channel": channel,
            "release_notes": self.release_notes,
            "download_url": self.download_url,
            "published_at": "2026-03-01T00:00:00Z",
        }


class UpdateService:
    """Checks for available updates and inspects release metadata."""

    def __init__(
        self,
        current_version: str = "1.0.0",
        update_port: UpdatePort | None = None,
    ) -> None:
        self.current_version = current_version
        self.update_port = update_port or FakeUpdateAdapter(latest_version=current_version)

    def check_for_updates(self, channel: str = "stable") -> AppVersionInfo:
        """Query latest release information and compare against current installation."""
        try:
            rel = self.update_port.fetch_latest_release(channel=channel)
            latest_v = str(rel.get("version", self.current_version))
            notes = str(rel.get("release_notes", ""))
            url = str(rel.get("download_url", ""))
            pub = str(rel.get("published_at", ""))
            newer = is_newer_version(latest_v, self.current_version)

            return AppVersionInfo(
                current_version=self.current_version,
                latest_version=latest_v,
                is_update_available=newer,
                channel=channel,
                release_notes=notes,
                download_url=url,
                published_at=pub,
            )
        except Exception as e:
            return AppVersionInfo(
                current_version=self.current_version,
                latest_version=self.current_version,
                is_update_available=False,
                channel=channel,
                release_notes=f"Update check failed: {e}",
            )
