SP-Farms Full Redesign V7
==========================

Target
------
Designed for the current SP-Farms architecture on main and for local installs
that already have the V5/V6 Action List patches.

V7 is a DIRECT DESKTOP CONSOLE redesign:
- no Quick Action card wall
- no visual step-flow strips
- no duplicate "easy mode" automation screen
- dense table-first management
- selected-context inspectors
- one primary Action List for normal automation
- Task Builder remains for advanced presets

Visible Layout
--------------
Home
  Metrics
  Recent Activity
  System Status
  Device Status

Accounts
  Header + metrics
  Small local tabs
  Row 1: Search + filters
  Row 2: status + Bulk + Action List + Account Actions + Add Account
  Dense accounts table
  Right selected-account inspector

Pages / Groups
  Metrics
  Search/filter toolbar
  Dense asset table
  Right asset inspector

Content
  Header
  Import Media
  Compose Post / Reel
  Tabs:
    Media
    Captions
    Drafts

Automation
  Action List       <- normal use
  Task Builder      <- advanced preset building
  Campaigns
  Schedule
  Approvals
  Queue

Devices
  Device Manager
  QA Profile Lab

Analytics
  Social Performance
  Device & Jobs

Settings
  compact left section navigation
  focused form panel
  persistent Save Settings

Design Direction
----------------
Dark charcoal desktop UI with:
- yellow/gold primary actions
- green success states
- blue only for informational state
- compact 32px table rows
- small 6-7px corner radius
- subtle borders
- clear selected rows
- no neon/glassmorphism
- no huge empty cards

Apply
-----
Extract this ZIP.

Put APPLY_FULL_REDESIGN_V7.py in:

C:\Users\Rg Gear\Desktop\SP-Farms\

Then run:

cd "C:\Users\Rg Gear\Desktop\SP-Farms"

.\.venv\Scripts\python.exe .\APPLY_FULL_REDESIGN_V7.py

Backup
------
The installer creates:

.full_redesign_v7_backup_YYYYMMDD-HHMMSS

Validate
--------
.\.venv\Scripts\python.exe -m ruff check sp_farms

.\.venv\Scripts\python.exe -m pytest tests/test_design_system.py tests/test_main_window.py tests/test_farm_reel_action_list.py -q

Run
---
.\.venv\Scripts\python.exe -m sp_farms.app.main

Important
---------
V7 changes UX/UI structure and presentation. It keeps the existing SP-Farms
services, job engine, device pool, account bindings, content services, analytics,
settings, and authorization/capability checks.

The Action List still uses the existing AutomationBuilderService and current
authorized AutomationStepType set.
