import contextlib
import re

from sp_farms.domain.providers import ConnectionTransport

_IP_PORT_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+$")
_EMULATOR_PATTERN = re.compile(r"^emulator-\d+$")
_BATTERY_LEVEL_PATTERN = re.compile(r"level:\s*(\d+)", re.IGNORECASE)
_BATTERY_POWERED_PATTERN = re.compile(
    r"(?:AC powered|USB powered|Wireless powered):\s*(true|false)", re.IGNORECASE
)


def classify_transport(serial: str) -> ConnectionTransport:
    raw = serial.strip()
    if not raw:
        return ConnectionTransport.UNKNOWN
    if _EMULATOR_PATTERN.match(raw) or raw.startswith("127.0.0.1:") or raw.startswith("localhost:"):
        return ConnectionTransport.EMULATOR
    if _IP_PORT_PATTERN.match(raw):
        return ConnectionTransport.WIFI
    return ConnectionTransport.USB


def parse_battery_status(dumpsys_output: str) -> tuple[int | None, bool | None]:
    """Parse output of `dumpsys battery`.

    Returns (battery_level, is_charging).
    """
    level: int | None = None
    level_match = _BATTERY_LEVEL_PATTERN.search(dumpsys_output)
    if level_match:
        with contextlib.suppress(ValueError):
            level = int(level_match.group(1))

    is_charging: bool | None = None
    powered_matches = _BATTERY_POWERED_PATTERN.findall(dumpsys_output)
    if powered_matches:
        is_charging = any(p.lower() == "true" for p in powered_matches)

    return level, is_charging
