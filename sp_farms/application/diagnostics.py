from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostics:
    app_version: str
    python_version: str
    operating_system: str
    database_path: Path
    log_path: Path
    providers: dict[str, str]
