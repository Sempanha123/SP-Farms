import os
import shutil
from collections.abc import Mapping
from pathlib import Path

_ENV_KEY = "SP_FARMS_MUMU_PATH"

_CANDIDATE_PATHS = (
    Path("C:/Program Files/Netease/MuMuPlayer-12.0/shell/MuMuManager.exe"),
    Path("C:/Program Files/Netease/MuMuPlayerGlobal-12.0/shell/MuMuManager.exe"),
    Path("C:/Program Files (x86)/Netease/MuMuPlayer-12.0/shell/MuMuManager.exe"),
    Path("C:/Program Files (x86)/Netease/MuMuPlayerGlobal-12.0/shell/MuMuManager.exe"),
    Path("D:/Program Files/Netease/MuMuPlayer-12.0/shell/MuMuManager.exe"),
    Path("D:/Program Files/Netease/MuMuPlayerGlobal-12.0/shell/MuMuManager.exe"),
    Path("C:/Program Files/Netease/MuMu/nemu/vmonitor/bin/MuMuManager.exe"),
    Path("C:/Program Files/Netease/MuMuPlayer-12.0/nx_device/MuMuManager.exe"),
)

_BINARY_NAMES = ("MuMuManager.exe", "MuMuManager", "mumu.exe", "mumu")


def find_mumu_executable(
    custom_path: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    env = os.environ if environ is None else environ

    # 1. Custom explicit path
    if custom_path is not None:
        p = Path(custom_path)
        if p.is_dir():
            for name in _BINARY_NAMES:
                candidate = p / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate.resolve()
        elif p.is_file() and os.access(p, os.X_OK):
            return p.resolve()

    # 2. Environment variable
    env_path = env.get(_ENV_KEY)
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            for name in _BINARY_NAMES:
                candidate = p / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate.resolve()
        elif p.is_file() and os.access(p, os.X_OK):
            return p.resolve()

    # 3. PATH resolution
    for name in _BINARY_NAMES:
        in_path = shutil.which(name, path=env.get("PATH"))
        if in_path:
            return Path(in_path).resolve()

    # 4. Standard candidate locations
    for candidate in _CANDIDATE_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    return None
