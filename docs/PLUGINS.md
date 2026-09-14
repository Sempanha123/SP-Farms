# SP-Farms Plugin & Provider SDK

SP-Farms features an extensible, isolated plugin architecture allowing third-party device providers, media processors, analytics exporters, and notification providers to integrate without modifying the application core.

## Plugin Types

1. **`device_provider`**: Integrates physical devices, cloud emulators, or specialized Android automation runners.
2. **`media_processor`**: Handles custom transcoding, watermarking, filters, or format conversions.
3. **`analytics_exporter`**: Exports aggregated post performance and device reliability metrics to external formats or endpoints.
4. **`notification_provider`**: Dispatches notifications to custom desktop channels, webhooks, or enterprise alerts.

## Plugin Manifest (`plugin.json`)

Every plugin directory must contain a `plugin.json` manifest:

```json
{
  "id": "com.example.custom_exporter",
  "name": "Custom Exporter",
  "version": "1.0.0",
  "plugin_type": "analytics_exporter",
  "entry_point": "my_module.plugins:MyExporterPlugin",
  "min_app_version": "1.0.0",
  "max_app_version": "2.0.0",
  "author": "Operator",
  "description": "Custom exporter plugin for SP-Farms",
  "capabilities": [
    "analytics.export.json"
  ],
  "permissions": [
    "network.access"
  ]
}
```

## Safety & Failure Isolation

- **Isolated Execution**: All plugin hooks run inside `PluginService.execute_safe(...)` error boundaries. If a plugin throws an uncaught exception or segmentation fault, the error is contained and recorded in the audit trail without terminating SP-Farms.
- **Strict Version Checking**: Plugins specifying incompatible `min_app_version` or `max_app_version` are safely marked as `FAILED` and prevented from initializing.
- **Zero Core Modification**: Plugins interact solely via protocol interfaces (`DeviceProviderPlugin`, `MediaProcessorPlugin`, `AnalyticsExporterPlugin`, `NotificationProviderPlugin`).
