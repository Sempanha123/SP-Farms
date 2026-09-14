import os
import shutil
from collections.abc import Mapping
from pathlib import Path


def find_adb_executable(
    custom_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    env = os.environ if environ is None else environ

    if custom_path is not None:
        p = Path(custom_path)
        if p.is_file() and os.access(p, os.X_OK):
            return p.resolve()
        if p.is_dir():
            cand = p / ("adb.exe" if os.name == "nt" else "adb")
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand.resolve()

    if "SP_FARMS_ADB_PATH" in env:
        p = Path(env["SP_FARMS_ADB_PATH"])
        if p.is_file() and os.access(p, os.X_OK):
            return p.resolve()
        cand = p / ("adb.exe" if os.name == "nt" else "adb")
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand.resolve()

    # Check ANDROID_HOME / ANDROID_SDK_ROOT
    for sdk_var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if sdk_var in env:
            sdk_dir = Path(env[sdk_var])
            cand = sdk_dir / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand.resolve()

    # Check system PATH
    which_path = shutil.which("adb", path=env.get("PATH"))
    if which_path:
        return Path(which_path).resolve()

    # Standard Windows platform-tools locations
    if os.name == "nt":
        candidates: list[Path] = []
        if "LOCALAPPDATA" in env:
            candidates.append(
                Path(env["LOCALAPPDATA"]) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
            )
        if "PROGRAMFILES" in env:
            candidates.append(
                Path(env["PROGRAMFILES"]) / "Android" / "android-sdk" / "platform-tools" / "adb.exe"
            )
        if "PROGRAMFILES(X86)" in env:
            candidates.append(
                Path(env["PROGRAMFILES(X86)"])
                / "Android"
                / "android-sdk"
                / "platform-tools"
                / "adb.exe"
            )
        for cand in candidates:
            if cand.is_file() and os.access(cand, os.X_OK):
                return cand.resolve()

    return None
