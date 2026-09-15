# Page -> Account -> Device Resolution Pipeline

## Resolution Hierarchy

In SP-Farms, operations on managed Pages automatically resolve upward through their owning Account and into stored Device Bindings:

```
+-------------------------------------------------------------+
|                          Page Row                           |
|       (e.g., "SP Cambo Store", page_id="1029384756")        |
+-------------------------------------------------------------+
                              |
                              | AssetPermission / Foreign Key
                              v
+-------------------------------------------------------------+
|                       Owning Account                        |
|        (e.g., "Shop Account 01", account_id="acc-01")       |
+-------------------------------------------------------------+
                              |
                              | AccountDeviceBinding
                              v
+-------------------------------------------------------------+
|                     Device Profile / ADB                    |
|           (e.g., provider="ldplayer", external_id="LD-03")  |
+-------------------------------------------------------------+
```

## Re-use vs. Restore Policy

1. **Active Device Check**:
   - If the account currently possesses an active workspace lock on a healthy emulator/device, that device is directly reused without repeating full workspace provisioning.
2. **Offline or Unbound Account**:
   - If no active device is bound, `DevicePoolService` acquires an available device following the configured policy (`BOUND_DEVICE_FIRST` -> `ANY_AVAILABLE`).
   - Legitimate account state, display preferences, and safe metadata are restored.
3. **Completion & Release**:
   - Devices remain reserved if chained automation steps exist in a batch workflow.
   - Released back to the shared pool upon job completion or error teardown.

## LSPosed QA Profile Independence

- Production Page and Account actions rely strictly on legitimate stored device assignments.
- LSPosed synthetic identity spoofing is permanently segregated in the **QA Profile Lab** and restricted exclusively to authorized operator test packages.
