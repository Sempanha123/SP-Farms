import contextlib
import json
from pathlib import Path

from sp_farms.domain.providers import EmulatorInstance


def map_mumu_serial(index: int, custom_port: int | None = None) -> str:
    """Map MuMu Player instance index to its ADB serial.

    MuMu Player 12 base port is 16384 with 32 port step per instance:
    Index 0: 127.0.0.1:16384
    Index 1: 127.0.0.1:16416
    Index n: 127.0.0.1:(16384 + n * 32)
    """
    if custom_port is not None and custom_port > 0:
        return f"127.0.0.1:{custom_port}"
    port = 16384 + (index * 32)
    return f"127.0.0.1:{port}"


def parse_mumu_instances(
    raw_output: str,
    install_path: Path | None = None,
) -> list[EmulatorInstance]:
    """Parse output from MuMuManager.

    Supports:
    1. JSON output from `MuMuManager.exe api -v all` or `info -v all`
    2. Tabular/key-value output lines
    """
    cleaned = raw_output.strip()
    if not cleaned:
        return []

    # Attempt JSON parsing first
    if (cleaned.startswith("[") and cleaned.endswith("]")) or (
        cleaned.startswith("{") and cleaned.endswith("}")
    ):
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                # May be wrapped in a dict like {"data": [...]} or dict of instances
                if "data" in data and isinstance(data["data"], list):
                    items = data["data"]
                else:
                    items = [data]
            elif isinstance(data, list):
                items = data
            else:
                items = []

            instances: list[EmulatorInstance] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                try:
                    raw_idx = item.get("index") or item.get("id") or 0
                    idx = int(raw_idx)
                    name = str(item.get("name") or item.get("title") or f"MuMuPlayer-{idx}")
                    # State could be "running", 1, True, or "started"
                    state_val = item.get("is_running", item.get("state", item.get("status")))
                    is_running = state_val in (1, True, "1", "running", "started")

                    custom_port: int | None = None
                    if "adb_port" in item and item["adb_port"]:
                        with contextlib.suppress(ValueError):
                            custom_port = int(item["adb_port"])

                    serial = map_mumu_serial(idx, custom_port)
                    pid = int(item["pid"]) if "pid" in item and str(item["pid"]).isdigit() else None

                    resolution: tuple[int, int] | None = None
                    if "width" in item and "height" in item:
                        try:
                            w = int(item["width"])
                            h = int(item["height"])
                            if w > 0 and h > 0:
                                resolution = (w, h)
                        except ValueError:
                            pass

                    dpi = int(item["dpi"]) if "dpi" in item and str(item["dpi"]).isdigit() else None

                    instances.append(
                        EmulatorInstance(
                            index=idx,
                            name=name,
                            adb_serial=serial,
                            is_running=is_running,
                            pid=pid,
                            resolution=resolution,
                            dpi=dpi,
                            install_path=install_path,
                        )
                    )
                except (ValueError, KeyError):
                    continue
            return instances
        except json.JSONDecodeError:
            pass

    # Line-based fallback
    # Format typically: index: 0, name: MuMuPlayer, status: running, port: 16384
    # or comma-separated: 0,MuMuPlayer,running,16384
    instances = []
    for line in cleaned.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            try:
                idx = int(parts[0])
                name = parts[1]
                status = parts[2].lower()
                is_running = status in ("1", "true", "running", "online", "started")
                port = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
                serial = map_mumu_serial(idx, port)

                instances.append(
                    EmulatorInstance(
                        index=idx,
                        name=name,
                        adb_serial=serial,
                        is_running=is_running,
                        install_path=install_path,
                    )
                )
            except ValueError:
                continue

    return instances
