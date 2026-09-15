SP-Farms Farm Reel Flow V5
============================

Goal
----
Make SP-Farms follow the simple Farm Reel action-list workflow while preserving
the existing SP-Farms services, job engine, device manager, account context,
network bindings, content system, and advanced automation builder.

Main operator flow
------------------
Accounts
  -> select one or more rows
  -> Action List...
  -> check actions
  -> configure the selected action on the right
  -> reorder selected actions
  -> Dry Run
  -> Start
  -> Job Queue

Automation
----------
Adds an "Action List" tab before Quick Mode / Advanced Builder.

The Action List exposes every existing SP-Farms AutomationStepType once:
- Restore Workspace
- Open Preferred App
- Health Check
- Refresh Authorized Asset Data
- Publish Text
- Publish Image
- Publish Multiple Images
- Publish Video
- Publish Reel
- Publish Story
- Publish Link
- Schedule Content
- Read Comments
- Reply to Selected Comments
- Moderate Comments
- Read Inbox
- Reply with Saved Reply
- Assign Inbox Item
- Add Internal Note
- Mark Resolved
- Post Analytics
- Reaction Analytics
- Share / View Metrics
- Follower Growth
- Backup Workspace
- Release Device
- Start Next Account

Each checked action can be configured and ordered. Common controls include:
- approval
- retry
- timeout
- delay metadata
- continue-on-error

The workflow is wired to the existing AutomationBuilderService:
validate_preset -> dry-run -> execute_preset -> persistent job queue.

Important
---------
A UI option being visible does not invent provider support. Existing capability
checks and provider/service configuration still decide whether a live operation
can execute.

If the platform requires verification/checkpoint handling, the intended flow is:
User action required -> operator completes verification -> resume.

This patch does not add CAPTCHA/checkpoint bypass, artificial engagement farming,
bulk friend adding, unsolicited bulk messaging, or fake Facebook device identity
evasion.

Apply
-----
1. Extract this ZIP.
2. Put APPLY_FARM_REEL_FLOW_V5.py in the SP-Farms repository root.
3. Run:

cd "C:\Users\Rg Gear\Desktop\SP-Farms"

.\.venv\Scripts\python.exe .\APPLY_FARM_REEL_FLOW_V5.py

The script creates:
.farm_reel_v5_backup_YYYYMMDD-HHMMSS

Validate
--------
.\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py tests/test_farm_reel_action_list.py -q

.\.venv\Scripts\python.exe -m ruff check sp_farms tests/test_farm_reel_action_list.py

Run
---
.\.venv\Scripts\python.exe -m sp_farms.app.main
