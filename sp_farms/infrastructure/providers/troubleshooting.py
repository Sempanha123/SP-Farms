from sp_farms.domain.devices import DeviceState
from sp_farms.domain.providers import TroubleshootingGuidance


def get_default_troubleshooting_guidance(state: DeviceState) -> TroubleshootingGuidance:
    match state:
        case DeviceState.UNAUTHORIZED:
            return TroubleshootingGuidance(
                state=state,
                title="Device is Unauthorized",
                steps=[
                    "Unlock your Android device screen.",
                    "Look for the 'Allow USB debugging?' pop-up prompt.",
                    "Check the box 'Always allow from this computer'.",
                    "Tap 'Allow' or 'OK'.",
                    "If no prompt appears, toggle USB Debugging off and on in Developer Options.",
                ],
            )
        case DeviceState.OFFLINE:
            return TroubleshootingGuidance(
                state=state,
                title="Device is Offline",
                steps=[
                    "Verify the USB cable is firmly connected to both PC and device.",
                    "Try using a different USB port or high-quality data cable.",
                    "Check that USB mode is File Transfer (MTP) or MIDI, not 'Charging only'.",
                    "If connected via Wi-Fi/TCP, ensure the device is on the same local network.",
                    "Restart the ADB server or reboot the device if it remains offline.",
                ],
            )
        case DeviceState.BOOTLOADER:
            return TroubleshootingGuidance(
                state=state,
                title="Device in Bootloader / Fastboot Mode",
                steps=[
                    "The device is currently in bootloader or recovery mode.",
                    "Reboot the device into the normal Android system.",
                ],
            )
        case DeviceState.AUTHORIZING | DeviceState.CONNECTING:
            return TroubleshootingGuidance(
                state=state,
                title="Device Connecting",
                steps=[
                    "The device is negotiating connection with the ADB daemon.",
                    "Wait a few seconds for the connection to complete.",
                ],
            )
        case DeviceState.ONLINE:
            return TroubleshootingGuidance(
                state=state,
                title="Device Ready",
                steps=["Device is online and fully operational."],
            )
        case _:
            return TroubleshootingGuidance(
                state=state,
                title="Device Status Unknown",
                steps=[
                    "Enable Developer Options (Settings > About Phone > Tap 'Build' 7 times).",
                    "Enable 'USB Debugging' in Settings > System > Developer Options.",
                    "Verify OEM USB drivers are installed on Windows 11.",
                ],
            )
