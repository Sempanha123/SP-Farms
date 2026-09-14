import importlib
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sp_farms.domain.plugins import (
    BasePlugin,
    PluginCapability,
    PluginExecutionResult,
    PluginManifest,
    PluginStatus,
    PluginType,
)

logger = logging.getLogger(__name__)

CURRENT_APP_VERSION = "1.0.0"


def _parse_version(v: str) -> tuple[int, ...]:
    parts = []
    for seg in v.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_version_compatible(app_version: str, min_version: str, max_version: str) -> bool:
    app_v = _parse_version(app_version)
    min_v = _parse_version(min_version)
    max_v = _parse_version(max_version)
    return min_v <= app_v <= max_v


@dataclass
class LoadedPluginContainer:
    manifest: PluginManifest
    instance: BasePlugin | None = None
    status: PluginStatus = PluginStatus.UNLOADED
    load_error: str | None = None


class PluginService:
    """Orchestrates discovery, validation, lifecycle, and failure isolation for plugins."""

    def __init__(
        self,
        plugins_dir: Path | None = None,
        app_version: str = CURRENT_APP_VERSION,
    ) -> None:
        self.plugins_dir = plugins_dir
        self.app_version = app_version
        self._plugins: dict[str, LoadedPluginContainer] = {}

    def register_instance(self, plugin: BasePlugin) -> bool:
        """Register and activate an in-memory or built-in plugin directly."""
        manifest = plugin.manifest
        if not is_version_compatible(
            self.app_version, manifest.min_app_version, manifest.max_app_version
        ):
            logger.warning(
                "Plugin %s is incompatible with app version %s",
                manifest.id,
                self.app_version,
            )
            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                instance=None,
                status=PluginStatus.FAILED,
                load_error=f"Incompatible with app version {self.app_version}",
            )
            return False

        try:
            plugin.initialize()
            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                instance=plugin,
                status=PluginStatus.ACTIVE,
            )
            return True
        except Exception as e:
            logger.exception("Failed initializing plugin %s: %s", manifest.id, e)
            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                instance=None,
                status=PluginStatus.FAILED,
                load_error=str(e),
            )
            return False

    def load_from_manifest_file(self, manifest_path: Path) -> bool:
        """Validate, load, and isolate a plugin from a plugin.json file."""
        if not manifest_path.exists():
            return False

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = PluginManifest.from_dict(data)
        except Exception as e:
            logger.error("Failed parsing plugin manifest at %s: %s", manifest_path, e)
            return False

        # Version check
        if not is_version_compatible(
            self.app_version, manifest.min_app_version, manifest.max_app_version
        ):
            err = (
                f"Requires app version [{manifest.min_app_version} - "
                f"{manifest.max_app_version}], current: {self.app_version}"
            )
            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                status=PluginStatus.FAILED,
                load_error=err,
            )
            return False

        # Safe dynamic load
        try:
            module_name, class_name = manifest.entry_point.rsplit(":", 1)
            mod = importlib.import_module(module_name)
            plugin_cls = getattr(mod, class_name)
            instance: BasePlugin = plugin_cls(manifest=manifest)
            instance.initialize()

            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                instance=instance,
                status=PluginStatus.ACTIVE,
            )
            return True
        except Exception as e:
            logger.exception("Safe load failed for plugin %s: %s", manifest.id, e)
            self._plugins[manifest.id] = LoadedPluginContainer(
                manifest=manifest,
                instance=None,
                status=PluginStatus.FAILED,
                load_error=str(e),
            )
            return False

    def discover_and_load_all(self) -> int:
        """Scan plugins directory for manifests and load all valid plugins."""
        if not self.plugins_dir or not self.plugins_dir.exists():
            return 0

        loaded = 0
        for manifest_file in self.plugins_dir.glob("**/plugin.json"):
            if self.load_from_manifest_file(manifest_file):
                loaded += 1
        return loaded

    def execute_safe(
        self,
        plugin_id: str,
        action: Callable[[Any], Any],
    ) -> PluginExecutionResult:
        """Execute a plugin method with complete failure isolation and error boundary."""
        container = self._plugins.get(plugin_id)
        if not container:
            return PluginExecutionResult(
                success=False,
                error=f"Plugin '{plugin_id}' not found",
            )

        if container.status != PluginStatus.ACTIVE or not container.instance:
            return PluginExecutionResult(
                success=False,
                error=f"Plugin '{plugin_id}' is not active (status: {container.status})",
            )

        start_time = time.perf_counter()
        try:
            result = action(container.instance)
            elapsed = (time.perf_counter() - start_time) * 1000
            return PluginExecutionResult(
                success=True,
                data=result,
                execution_time_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error("Isolated plugin failure in %s: %s", plugin_id, exc)
            return PluginExecutionResult(
                success=False,
                error=str(exc),
                execution_time_ms=round(elapsed, 2),
            )

    def get_plugins_by_type(self, plugin_type: PluginType) -> list[BasePlugin]:
        """Return all active plugin instances of a specified type."""
        return [
            c.instance
            for c in self._plugins.values()
            if c.status == PluginStatus.ACTIVE
            and c.instance is not None
            and c.manifest.plugin_type == plugin_type
        ]

    def get_plugins_with_capability(self, cap: PluginCapability) -> list[BasePlugin]:
        """Return active plugins declaring a given capability."""
        return [
            c.instance
            for c in self._plugins.values()
            if c.status == PluginStatus.ACTIVE
            and c.instance is not None
            and cap in c.manifest.capabilities
        ]

    def list_containers(self) -> Sequence[LoadedPluginContainer]:
        return list(self._plugins.values())

    def unload(self, plugin_id: str) -> bool:
        """Gracefully shutdown and unload a plugin."""
        container = self._plugins.get(plugin_id)
        if not container:
            return False

        if container.instance:
            try:
                container.instance.shutdown()
            except Exception as e:
                logger.warning("Error shutting down plugin %s: %s", plugin_id, e)

        container.status = PluginStatus.UNLOADED
        container.instance = None
        return True


# -------------------------------------------------------------------------
# Built-in Sample Plugins
# -------------------------------------------------------------------------

class SampleAnalyticsExporterPlugin:
    """Built-in reference plugin for JSON analytics exports."""

    def __init__(self, manifest: PluginManifest | None = None) -> None:
        self.manifest = manifest or PluginManifest(
            id="sp_farms.sample_analytics_exporter",
            name="Sample Analytics Exporter",
            version="1.0.0",
            plugin_type=PluginType.ANALYTICS_EXPORTER,
            entry_point="sp_farms.application.plugin_service:SampleAnalyticsExporterPlugin",
            capabilities=(PluginCapability.ANALYTICS_EXPORT_JSON,),
            description="Reference implementation exporting analytics to structured JSON",
        )
        self.initialized = False

    def initialize(self) -> None:
        self.initialized = True

    def shutdown(self) -> None:
        self.initialized = False

    def export_metrics(self, data: Sequence[dict[str, Any]], destination: str) -> str:
        out = json.dumps({"metrics": list(data), "count": len(data)}, indent=2)
        if destination:
            with open(destination, "w", encoding="utf-8") as f:
                f.write(out)
        return out


class SampleNotificationPlugin:
    """Built-in reference plugin for desktop notifications."""

    def __init__(self, manifest: PluginManifest | None = None) -> None:
        self.manifest = manifest or PluginManifest(
            id="sp_farms.sample_notifier",
            name="Sample Notification Provider",
            version="1.0.0",
            plugin_type=PluginType.NOTIFICATION_PROVIDER,
            entry_point="sp_farms.application.plugin_service:SampleNotificationPlugin",
            capabilities=(PluginCapability.NOTIFICATION_DESKTOP,),
            description="Reference implementation for notifications",
        )
        self.dispatched_alerts: list[tuple[str, str, str]] = []

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        self.dispatched_alerts.clear()

    def dispatch_alert(self, title: str, message: str, severity: str) -> bool:
        self.dispatched_alerts.append((title, message, severity))
        return True
