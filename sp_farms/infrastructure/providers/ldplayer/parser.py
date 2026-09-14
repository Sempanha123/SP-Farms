from pathlib import Path

from sp_farms.domain.providers import EmulatorInstance


def map_ldplayer_serial(index: int) -> str:
    """Standard LDPlayer ADB serial mapping based on instance index.

    LDPlayer maps index 0 to emulator-5554, index 1 to emulator-5556, etc.,
    or alternatively 127.0.0.1:(5555 + index * 2). We return the emulator-X format
    which matches the default adb device listing from LDPlayer.
    """
    base_port = 5554 + (index * 2)
    return f"emulator-{base_port}"


def parse_ldplayer_list(
    raw_output: str,
    install_path: Path | None = None,
) -> list[EmulatorInstance]:
    """Parse output of `ldconsole.exe list2`.

    Format (comma-separated lines):
    <index>,<title>,<top_window_handle>,<bind_window_handle>,<android_started>,<pid>,<vbox_pid>[,<width>,<height>,<dpi>]
    android_started is "1" if running, "0" or "-1" otherwise.
    """
    instances: list[EmulatorInstance] = []

    for line in raw_output.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue

        try:
            index = int(parts[0])
            name = parts[1]
            is_running = parts[4] == "1"

            has_pid = len(parts) > 5 and parts[5].isdigit() and int(parts[5]) > 0
            pid = int(parts[5]) if has_pid else None

            has_vbox = len(parts) > 6 and parts[6].isdigit() and int(parts[6]) > 0
            vbox_pid = int(parts[6]) if has_vbox else None

            resolution: tuple[int, int] | None = None
            dpi: int | None = None
            if len(parts) >= 10:
                try:
                    w = int(parts[7])
                    h = int(parts[8])
                    dpi_val = int(parts[9])
                    if w > 0 and h > 0:
                        resolution = (w, h)
                    if dpi_val > 0:
                        dpi = dpi_val
                except ValueError:
                    pass

            adb_serial = map_ldplayer_serial(index)

            instances.append(
                EmulatorInstance(
                    index=index,
                    name=name,
                    adb_serial=adb_serial,
                    is_running=is_running,
                    pid=pid,
                    vbox_pid=vbox_pid,
                    resolution=resolution,
                    dpi=dpi,
                    install_path=install_path,
                )
            )
        except (ValueError, IndexError):
            continue

    return instances
