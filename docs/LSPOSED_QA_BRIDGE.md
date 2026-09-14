# LSPosed QA Bridge Contract

This subsystem is for applications/devices the operator owns or is explicitly authorized to test. It is not intended for platform evasion, account creation, or bypassing third-party security systems.

## Version 1

SP-Farms is coupled only to `QAProfileReloadBridge`; an operator-owned LSPosed module implements the Android side.

- Profile path: `/data/local/tmp/sp_farms_qa/profile.json`
- Status path: `/data/local/tmp/sp_farms_qa/status.json`
- File mode: `600`
- Reload action: `com.spfarms.qa.action.RELOAD_PROFILE_V1`
- Encoding: UTF-8 JSON
- Profile `schema_version`: `1`
- Bridge `bridge_version`: `1`

The profile document contains `schema_version`, `bridge_version`, `target_package`, and `profile`. The module must reject packages outside its own matching allowlist and visibly mark overrides as test-only.

After accepting a reload broadcast, the module writes status JSON:

```json
{
  "bridge_version": 1,
  "loaded": true,
  "profile_id": "profile-uuid",
  "target_package": "com.example.ownedapp"
}
```

SP-Farms verifies that status rather than treating file presence as proof of activation. Restore removes the profile file and emits the same reload action; the module must discard overrides and return to actual/default values.

ADB push uses an argument array. Remote shell commands contain fixed project constants only. Temporary local JSON is deleted in a `finally` block after success or failure.
