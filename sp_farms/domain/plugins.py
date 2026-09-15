from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class PluginType(StrEnum):
    DEVICE_PROVIDER = "device_provider"
    MEDIA_PROCESSOR = "media_processor"
    ANALYTICS_EXPORTER = "analytics_exporter"
    NOTIFICATION_PROVIDER = "notification_provider"


class PluginCapability(StrEnum):
    DEVICE_DISCOVERY = "device.discovery"
    DEVICE_LIFECYCLE = "device.lifecycle"
    DEVICE_CONTROL = "device.control"
    MEDIA_TRANSCODE = "media.transcode"
    MEDIA_WATERMARK = "media.watermark"
    MEDIA_METADATA = "media.metadata"
    ANALYTICS_EXPORT_CSV = "analytics.export.csv"
    ANALYTICS_EXPORT_JSON = "analytics.export.json"
    ANALYTICS_EXPORT_REMOTE = "analytics.export.remote"
    NOTIFICATION_DESKTOP = "notification.desktop"
    NOTIFICATION_WEBHOOK = "notification.webhook"


class PluginStatus(StrEnum):
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ACTIVE = "active"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    id: str
    name: str
    version: str
    plugin_type: PluginType
    entry_point: str
    min_app_version: str = "1.0.0"
    max_app_version: str = "99.0.0"
    author: str = "Unknown"
    description: str = ""
    capabilities: tuple[PluginCapability, ...] = ()
    permissions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PluginManifest":
        p_type = PluginType(data["plugin_type"])
        caps = tuple(PluginCapability(c) for c in data.get("capabilities", ()))
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            plugin_type=p_type,
            entry_point=str(data["entry_point"]),
            min_app_version=str(data.get("min_app_version", "1.0.0")),
            max_app_version=str(data.get("max_app_version", "99.0.0")),
            author=str(data.get("author", "Unknown")),
            description=str(data.get("description", "")),
            capabilities=caps,
            permissions=tuple(str(p) for p in data.get("permissions", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "plugin_type": self.plugin_type.value,
            "entry_point": self.entry_point,
            "min_app_version": self.min_app_version,
            "max_app_version": self.max_app_version,
            "author": self.author,
            "description": self.description,
            "capabilities": [c.value for c in self.capabilities],
            "permissions": list(self.permissions),
        }


@dataclass(frozen=True, slots=True)
class PluginExecutionResult:
    success: bool
    data: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0


# -------------------------------------------------------------------------
# Plugin Protocols
# -------------------------------------------------------------------------


@runtime_checkable
class BasePlugin(Protocol):
    manifest: PluginManifest

    def initialize(self) -> None:
        """Initialize resources required by plugin."""
        ...

    def shutdown(self) -> None:
        """Clean up any open sockets or worker threads."""
        ...


@runtime_checkable
class DeviceProviderPlugin(BasePlugin, Protocol):
    def list_devices(self) -> Sequence[dict[str, Any]]:
        """Return list of discovered hardware or emulator devices."""
        ...

    def launch_instance(self, instance_id: str) -> bool:
        """Boot emulator or initialize device."""
        ...

    def stop_instance(self, instance_id: str) -> bool:
        """Stop device or emulator."""
        ...


@runtime_checkable
class MediaProcessorPlugin(BasePlugin, Protocol):
    def process_media(self, input_path: str, output_path: str, options: Mapping[str, Any]) -> str:
        """Process, watermark, or transcode an image or video asset."""
        ...


@runtime_checkable
class AnalyticsExporterPlugin(BasePlugin, Protocol):
    def export_metrics(self, data: Sequence[Mapping[str, Any]], destination: str) -> str:
        """Export analytics metrics to specified destination."""
        ...


@runtime_checkable
class NotificationProviderPlugin(BasePlugin, Protocol):
    def dispatch_alert(self, title: str, message: str, severity: str) -> bool:
        """Send notification alert."""
        ...
