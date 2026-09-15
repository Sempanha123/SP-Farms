# Context-Aware Universal Action Modal

## Overview

The **ContextActionDialog** is SP-Farms' universal action interface, bridging table selections directly to actionable operations without redundant target re-selection.

## Core Guarantees

1. **Zero-Reselect**:
   - The selected rows in Accounts, Pages, or Devices tables serve as the definitive target context.
   - A persistent, read-only `"Using:"` summary bar displays the exact inferred target bindings:
     ```text
     Using: Account: Shop Account 01 | Page: SP Cambo Store | Device: ldplayer:LD-03 | App: Facebook | State: Ready
     ```

2. **Context-Sensitive Tabs**:
   - Tabs are dynamically generated based on the source entity and its authorized capabilities.
   - **Account Context**: Overview, Restore Workspace, Content, Post Feed, Video, Reel, Story, Comments, Inbox, Analytics, Backup, Device Binding, Security, Advanced.
   - **Page Context**: Overview, Content, Post Feed, Video, Reel, Story, Comments, Inbox, Analytics, Schedule, Backup, Connected Account, Device Binding, Advanced.
   - **Device Context**: Overview, Assigned Account, Launch App, Health, Screenshot, Logs, Backup, Release Device, QA Profile Lab (restricted), Advanced.

3. **Strict LSPosed QA Profile Security Boundary**:
   - **Production Workspaces**: Only legitimate device assignments, display configurations, and valid token states are restored.
   - **QA Profile Lab**: Synthetic LSPosed device identities are strictly quarantined to authorized test packages and prohibited from targeting Facebook, Facebook Lite, or Instagram.

4. **Non-Blocking Architecture**:
   - All long-running actions (ADB commands, Meta HTTP requests, workspace compression) execute on background threads via `AsyncActionWorker` and `QThreadPool`.
   - Real-time event streams update progress bars without freezing the Qt GUI thread.
   - Closing the modal does not abort background execution.

## Modal -> Job Engine Flow

```
+-------------------------------------------------------------+
|                     ContextActionDialog                     |
|  [Tabs: Restore | Post | Reel | Comments | Backup | Device]   |
+-------------------------------------------------------------+
                              |
                     (Run / Batch Action)
                              v
                  AsyncActionWorker (QRunnable)
                  Dispatched to QThreadPool
                              |
                              +--------> JobService / WorkerSupervisor
                              |          - Atomic workspace lock
                              |          - Background ADB / HTTP execution
                              |
                     Signals / Slots
              (started, progress, target_completed, finished)
                              |
                              v
                     ContextActionDialog
              - Real-time progress bar & label
              - Non-blocking responsive UI
```
