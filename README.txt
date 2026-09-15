SP-Farms Reference UI V4
========================

This is a self-contained code patch for the merged SP-Farms project.

Reference images included:
- design/reference/sp-farms-ui-reference.png
- design/reference/each-tab.png

Main changes
------------
- Top navigation gets compact icons + live date/time.
- Home becomes a dense operational dashboard.
- Left Device Manager rail is rebuilt closer to the reference:
  device search/filter, selected device details, CPU/RAM/network/account,
  Start/Stop/Restart, launch/screenshot, Start All/Stop All, and shortcuts.
- Accounts gets a visible workflow:
  Select -> Resolve Device/Network -> Restore -> Actions -> Monitor.
- Content gets a visible workflow:
  Media -> Compose -> Destination -> Dry Run -> Publish.
- Automation gets Quick Mode before the existing Advanced Builder.
- Context Account Actions uses a left vertical tab rail.
- Post tab gets a two-column editor + live caption preview.
- Existing backend/services remain in place.
- Existing Advanced Builder remains available.

Apply
-----
Put APPLY_REFERENCE_UI_V4.py in the SP-Farms repository root and run:

    .\.venv\Scripts\python.exe .\APPLY_REFERENCE_UI_V4.py

The patch creates a rollback folder first:

    .reference_ui_v4_backup_YYYYMMDD-HHMMSS

Then validate:

    .\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py -q
    .\.venv\Scripts\python.exe -m ruff check sp_farms
    .\.venv\Scripts\python.exe -m sp_farms.app.main

Notes
-----
The patch is designed against the currently merged main branch structure discussed
in chat. It is root-safe: the replacement payloads are embedded inside the script,
so it does not copy source files onto themselves.

The UI follows the dark charcoal + yellow/gold reference direction and keeps
tables dense. It does not add security-bypass or artificial-engagement behavior.
