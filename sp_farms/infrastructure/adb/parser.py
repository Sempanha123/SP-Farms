import re

from sp_farms.domain.devices import DeviceInfo, DeviceState


def parse_devices_output(output: str) -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    lines = output.strip().splitlines()

    for line in lines:
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("List of devices") or cleaned.startswith("*"):
            continue

        parts = cleaned.split()
        if len(parts) < 2:
            continue

        serial = parts[0]
        status_str = parts[1]
        state = DeviceState.from_adb_status(status_str)

        model: str | None = None
        for part in parts[2:]:
            if part.startswith("model:"):
                model = part.split(":", 1)[1].replace("_", " ")
                break

        devices.append(
            DeviceInfo(
                serial=serial,
                state=state,
                model=model,
            )
        )

    return devices


def parse_resolution(output: str) -> tuple[int, int] | None:
    match = re.search(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", output)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def parse_android_version(output: str) -> str | None:
    cleaned = output.strip()
    return cleaned if cleaned else None


def parse_sdk_version(output: str) -> int | None:
    cleaned = output.strip()
    try:
        return int(cleaned)
    except ValueError:
        return None
