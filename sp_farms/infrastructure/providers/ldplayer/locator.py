import os
import shutil
from collections.abc import Mapping
from pathlib import Path

_ENV_KEY = "SP_FARMS_LDPLAYER_PATH"

_CANDIDATE_PATHS = (
    Path("C:/LDPlayer/LDPlayer9/ldconsole.exe"),
    Path("C:/leidian/LDPlayer9/ldconsole.exe"),
    Path("C:/Program Files/LDPlayer/LDPlayer9/ldconsole.exe"),
    Path("C:/Program Files (x86)/LDPlayer/LDPlayer9/ldconsole.exe"),
    Path("D:/LDPlayer/LDPlayer9/ldconsole.exe"),
    Path("D:/leidian/LDPlayer9/ldconsole.exe"),
    Path("C:/LDPlayer/LDPlayer4/ldconsole.exe"),
    Path("C:/leidian/LDPlayer4/ldconsole.exe"),
    Path("C:/Program Files/dnplayerext2/dnconsole.exe"),
)


def find_ldplayer_executable(
    custom_path: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path | None:
    env = os.environ if environ is None else environ

    # 1. Custom explicit path
    if custom_path is not None:
        p = Path(custom_path)
        if p.is_dir():
            for name in ("ldconsole.exe", "dnconsole.exe", "ldconsole", "dnconsole"):
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
            for name in ("ldconsole.exe", "dnconsole.exe", "ldconsole", "dnconsole"):
                candidate = p / name
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return candidate.resolve()
        elif p.is_file() and os.access(p, os.X_OK):
            return p.resolve()

    # 3. PATH resolution
    for name in ("ldconsole.exe", "dnconsole.exe", "ldconsole", "dnconsole"):
        in_path = shutil.which(name, path=env.get("PATH"))
        if in_path:
            return Path(in_path).resolve()

    # 4. Standard candidate locations
    for candidate in _CANDIDATE_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()

    return None
