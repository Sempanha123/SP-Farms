# Selection Context Architecture

## Overview

The `SelectionContext` domain entity and `SelectionContextService` provide unified contextual target resolution across Accounts, Pages, Groups, and Devices in SP-Farms.

## Selection Sources & Target Types

```
[Accounts Table]  -----> SelectionSource.ACCOUNTS ----> TargetType.ACCOUNT
[Pages Table]     -----> SelectionSource.PAGES    ----> TargetType.PAGE
[Groups Table]    -----> SelectionSource.GROUPS   ----> TargetType.GROUP
[Devices Table]   -----> SelectionSource.DEVICES  ----> TargetType.DEVICE
```

## Resolution Attributes

When rows are selected, `SelectionContextService.resolve_context()` evaluates:
- **`resolved_targets`**: Fully qualified `ResolvedTarget` instances containing:
  - `target_id`, `target_type`, `display_name`
  - `owning_account_id` and `owning_account_name`
  - `bound_device_id` and `bound_device_provider`
  - `preferred_app` (`facebook`, `facebook_lite`, `browser`)
  - `auth_state` (`ready`, `needs_reauth`, `degraded`)
  - `capabilities` (`TargetCapability` flags)
- **`common_capabilities`**: Capability flags shared by **all** selected targets.
- **`mixed_capabilities`**: Capability flags supported by **some** but not all targets.
- **`inferred_account_ids`**: Distinct account IDs involved across all selected targets.
- **`inferred_device_ids`**: Distinct device profile IDs bound to the targets.

## Multi-Select Capability Gating

When operating in batch mode:
- Actions requiring capabilities only present in `mixed_capabilities` are flagged with warnings or automatically filtered to eligible targets only.
- Pre-flight dry run simulation verifies the execution matrix across all resolved targets prior to dispatch.
