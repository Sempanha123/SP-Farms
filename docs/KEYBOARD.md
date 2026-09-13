# Keyboard Operation

SP-Farms exposes navigation and common actions through a central command registry. Duplicate command IDs and shortcut collisions fail during registration.

- `Ctrl+K`: open the searchable command palette.
- `Ctrl+/`: open keyboard shortcut help.
- `Alt+1` through `Alt+9`: open Home, Accounts, Pages, Groups, Content, Automation, Devices, Analytics, or Settings.
- `Escape`: close transient dialogs and overlays through standard Qt behavior.

The command palette searches command titles, identifiers, and keywords. Enter runs the selected command. Opening the palette moves keyboard focus directly to search.

Notifications enter the notification-center model and may also surface as temporary toasts. Long operations use a non-modal progress overlay; provider, network, disk, and database work remains outside the UI thread.
