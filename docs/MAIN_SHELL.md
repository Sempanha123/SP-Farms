# Main Shell

The main window follows the reference hierarchy:

1. compact top navigation for Home, Accounts, Pages, Groups, Content, Automation, Devices, Analytics, and Settings;
2. a resizable left Device Manager rail;
3. the central dense management workspace;
4. an optional right Job Queue drawer;
5. a compact workspace status row.

Accounts is the initial section. Window geometry, theme, and Job Queue visibility persist through `QSettings`. The minimum shell size is 1024 × 680; layouts and splitters absorb additional space without fixed-position controls.

The shell owns presentation state only. It receives the composed `ApplicationContext`, invokes application services through that context, and closes process resources when the window closes. Database sessions and long-running provider work never belong in window classes.
