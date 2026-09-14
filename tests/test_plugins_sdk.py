import json
from pathlib import Path
from typing import Any

from sp_farms.application.plugin_service import (
    PluginService,
    SampleAnalyticsExporterPlugin,
    SampleNotificationPlugin,
    is_version_compatible,
)
from sp_farms.domain.plugins import (
    DeviceProviderPlugin,
    PluginCapability,
    PluginManifest,
    PluginStatus,
    PluginType,
)


class CrashingPlugin:
    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def do_risky_task(self) -> None:
        raise RuntimeError("Fatal internal hardware bus exception")


class CustomDevicePlugin:
    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest
        self.started = False

    def initialize(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.started = False

    def list_devices(self) -> list[dict[str, Any]]:
        return [{"id": "custom-dev-1", "name": "Custom Virtual Android"}]

    def launch_instance(self, instance_id: str) -> bool:
        return instance_id == "custom-dev-1"

    def stop_instance(self, instance_id: str) -> bool:
        return True


def test_version_compatibility_helper():
    assert is_version_compatible("1.0.0", "1.0.0", "2.0.0") is True
    assert is_version_compatible("1.5.2", "1.0.0", "2.0.0") is True
    assert is_version_compatible("0.9.9", "1.0.0", "2.0.0") is False
    assert is_version_compatible("2.1.0", "1.0.0", "2.0.0") is False


def test_sample_built_in_plugins():
    service = PluginService(app_version="1.0.0")
    analytics_plug = SampleAnalyticsExporterPlugin()
    notify_plug = SampleNotificationPlugin()

    assert service.register_instance(analytics_plug) is True
    assert service.register_instance(notify_plug) is True

    # Test Analytics Plugin Execution via execute_safe
    result = service.execute_safe(
        "sp_farms.sample_analytics_exporter",
        lambda p: p.export_metrics([{"posts": 10, "reach": 500}], destination=""),
    )
    assert result.success is True
    assert "metrics" in result.data
    assert result.execution_time_ms >= 0.0

    # Test Notification Plugin Execution
    result_notify = service.execute_safe(
        "sp_farms.sample_notifier",
        lambda p: p.dispatch_alert("Job Complete", "Post published", "info"),
    )
    assert result_notify.success is True
    assert len(notify_plug.dispatched_alerts) == 1


def test_plugin_failure_isolation():
    service = PluginService(app_version="1.0.0")
    manifest = PluginManifest(
        id="test.crashing_plugin",
        name="Crashing Plugin",
        version="1.0.0",
        plugin_type=PluginType.DEVICE_PROVIDER,
        entry_point="fake:entry",
    )
    plugin = CrashingPlugin(manifest)
    service.register_instance(plugin)

    # Executing action that throws MUST NOT raise exception; must be isolated
    result = service.execute_safe("test.crashing_plugin", lambda p: p.do_risky_task())
    assert result.success is False
    assert "Fatal internal hardware bus exception" in str(result.error)
    assert result.execution_time_ms >= 0.0


def test_incompatible_version_rejected():
    service = PluginService(app_version="1.0.0")
    manifest = PluginManifest(
        id="future.plugin",
        name="Future Plugin",
        version="2.0.0",
        plugin_type=PluginType.MEDIA_PROCESSOR,
        entry_point="future:entry",
        min_app_version="2.0.0",
        max_app_version="3.0.0",
    )
    plugin = CrashingPlugin(manifest)
    registered = service.register_instance(plugin)
    assert registered is False

    containers = service.list_containers()
    future_c = next((c for c in containers if c.manifest.id == "future.plugin"), None)
    assert future_c is not None
    assert future_c.status == PluginStatus.FAILED
    assert "Incompatible" in str(future_c.load_error)


def test_manifest_discovery_and_safe_loading(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    plugin_subfolder = plugins_dir / "custom_dev"
    plugin_subfolder.mkdir()

    manifest_content = {
        "id": "com.spfarms.custom_dev",
        "name": "Custom Dev Plugin",
        "version": "1.0.0",
        "plugin_type": "device_provider",
        "entry_point": "tests.test_plugins_sdk:CustomDevicePlugin",
        "min_app_version": "1.0.0",
        "max_app_version": "1.9.9",
        "capabilities": ["device.discovery", "device.control"],
        "author": "Operator",
    }
    (plugin_subfolder / "plugin.json").write_text(json.dumps(manifest_content), encoding="utf-8")

    service = PluginService(plugins_dir=plugins_dir, app_version="1.0.0")
    loaded_count = service.discover_and_load_all()
    assert loaded_count == 1

    # Verify query by capability and type
    dev_plugins = service.get_plugins_by_type(PluginType.DEVICE_PROVIDER)
    assert len(dev_plugins) == 1
    assert isinstance(dev_plugins[0], DeviceProviderPlugin)

    cap_plugins = service.get_plugins_with_capability(PluginCapability.DEVICE_DISCOVERY)
    assert len(cap_plugins) == 1

    # Execute safe call on dynamically loaded plugin
    exec_res = service.execute_safe("com.spfarms.custom_dev", lambda p: p.list_devices())
    assert exec_res.success is True
    assert exec_res.data[0]["id"] == "custom-dev-1"

    # Unload
    assert service.unload("com.spfarms.custom_dev") is True
    assert len(service.get_plugins_by_type(PluginType.DEVICE_PROVIDER)) == 0


def test_invalid_manifest_handling(tmp_path: Path):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    # Corrupted JSON
    corrupt_file = plugins_dir / "plugin.json"
    corrupt_file.write_text("{corrupt: json}", encoding="utf-8")

    service = PluginService(plugins_dir=plugins_dir)
    assert service.load_from_manifest_file(corrupt_file) is False

    # Invalid plugin type
    bad_type = {
        "id": "bad",
        "name": "bad",
        "version": "1.0.0",
        "plugin_type": "unrecognized_unknown_type",
        "entry_point": "a:b",
    }
    corrupt_file.write_text(json.dumps(bad_type), encoding="utf-8")
    assert service.load_from_manifest_file(corrupt_file) is False
