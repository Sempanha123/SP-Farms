SP-Farms UX/UI V3 — FLOW UPDATE
================================

This is a CODE PATCH for the currently merged SP-Farms main branch.

Designed against merge:
43512cf67b25dde47fed7a47fc1322c9e5fdf237

MAIN FLOW
---------
Home now makes this normal operator path obvious:

Account
  -> Device + Network
  -> Restore Workspace
  -> Action
  -> Monitor

UX/UI updates
-------------
- Home: clickable 5-step Quick Flow
- Home: compact metrics, Fast Launch, System Health, Recent Jobs, Device Snapshot
- Accounts: visible Select -> Resolve -> Restore -> Actions -> Monitor flow
- Content: Media -> Compose -> Destination -> Dry Run -> Publish flow
- Automation: new Quick Mode before the existing Advanced Builder
- Context Action dialog: tabs move to a left vertical rail like the reference image
- Advanced Builder: removes several heavy hard-coded blue/slate panels
- Device rail / bottom footer: tighter desktop density
- Theme keeps the locked SP-Farms colors:
  - #0D1113 background
  - #121719 surface
  - #F4C915 yellow
  - #25D06F green success

APPLY
-----
1. Extract this ZIP.
2. Open PowerShell in your real SP-Farms repo:

cd "C:\Users\Rg Gear\Desktop\SP-Farms"

3. Run the patch:

.\.venv\Scripts\python.exe "C:\PATH\TO\SP-Farms-UX-UI-V3-Flow\APPLY_UX_UI_V3.py"

The patch automatically creates:
.ux_ui_v3_backup_YYYYMMDD-HHMMSS

TEST
----
.\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py tests/test_quick_automation_workspace.py -q

.\.venv\Scripts\python.exe -m ruff check sp_farms tests

RUN
---
.\.venv\Scripts\python.exe -m sp_farms.app.main

This patch reuses your existing services and jobs. It does not replace the backend.
