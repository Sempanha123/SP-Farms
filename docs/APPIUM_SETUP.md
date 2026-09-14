# Appium 2 & UiAutomator2 Android UI Automation Setup

This document describes the setup, configuration, and execution guidelines for Appium 2 Android UI automation within **SP-Farms**.

---

## 1. Architecture Overview

```
SP-Farms Persistent Job Engine
       │
       ▼
 Worker Supervisor (Background threads, non-GUI)
       │
       ▼
 Device Pool & Reservation Lock
       │
       ├── ADB CLI / Low-level operations (reboot, install, forward)
       │
       └── Appium 2 Server (W3C WebDriver REST API: /session)
              │
              ▼
       UiAutomator2 Driver (systemPort per device)
              │
              ▼
       Target Android UI (LDPlayer, MuMu, Physical Devices)
```

- **Low-level device management**: Uses ADB commands for device lifecycle, APK deployment, port forwards, and log streaming.
- **High-level UI automation**: Managed via Appium 2 W3C REST endpoints driving `io.appium.uiautomator2.server`.
- **Concurrency Isolation**: Each reserved device receives an isolated Appium session with dedicated `systemPort` (range 8200..8299).
- **GUI Safety**: Appium and ADB network calls execute strictly off the Qt GUI thread within worker threads or `QThreadPool` runnables.

---

## 2. Prerequisites & Installation

### Appium 2 Core
Ensure Node.js (v18+) and npm are installed:

```bash
# Install Appium 2 globally
npm install -g appium

# Verify version
appium --version
# Expected: 2.x.x
```

### UiAutomator2 Driver
Install the official UiAutomator2 driver:

```bash
appium driver install uiautomator2

# Verify installation
appium driver list --installed
```

### Android SDK & ADB
Ensure Android SDK Build-Tools and Platform-Tools are installed and exported in your environment:
- `ANDROID_HOME` or `ANDROID_SDK_ROOT`
- Path entries for `%ANDROID_HOME%\platform-tools` and `%ANDROID_HOME%\cmdline-tools\latest\bin`

Verify ADB detection:
```bash
adb devices
```

---

## 3. Starting Appium Server

Appium 2 can be run as a centralized local daemon or started automatically by SP-Farms:

```bash
# Start default Appium 2 server on port 4723
appium --address 127.0.0.1 --port 4723 --log-level info
```

---

## 4. Emulator & Physical Device Setup

### LDPlayer
1. Enable Root and ADB debugging in LDPlayer settings.
2. Verify connection:
   ```bash
   adb connect 127.0.0.1:5555
   ```

### MuMu Player
1. MuMu 12 typically listens on port 16384 or 7555:
   ```bash
   adb connect 127.0.0.1:16384
   ```

### Physical Android Devices
1. Enable Developer Options & USB Debugging.
2. Enable "Install via USB" and "USB debugging (Security settings)" if on MIUI/ColorOS/HyperOS.
3. Connect via USB and authorize the RSA host fingerprint.

---

## 5. Page Object Model & Mobile Actions

All UI interaction workflows should inherit from `BaseScreen` and use structured selectors:

```python
from sp_farms.application.automation.mobile_driver import MobileDriver
from sp_farms.infrastructure.appium.page_objects.facebook_screen import FacebookHomeScreen

def run_post_flow(driver: MobileDriver):
    home = FacebookHomeScreen(driver)
    home.wait_for_screen(timeout_seconds=10.0)
    composer = home.open_composer()
    composer.set_post_text("Automated update via SP-Farms")
    composer.submit_post()
```

---

## 6. Health Checks, Failure Recovery & Screenshots

- **Health Check**: `AppiumServerManager.check_health()` checks Appium `/status`.
- **Automatic Failure Screenshots**: In case of timeouts or exceptions during actions, `MobileDriver` automatically saves PNG screenshots to `artifacts/automation/`.
- **Session Cleanup**: When a device lock is released via `AppiumJobExecutor` or `AppiumSessionManager.end_session()`, the W3C session is deleted and system ports are freed immediately.
