from dataclasses import dataclass
from pathlib import Path

LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class AppConfig:
    environment: str
    log_level: str
    database_path: Path
    log_path: Path
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 5
    adb_path: Path | None = None
    ldplayer_path: Path | None = None

    def __post_init__(self) -> None:
        if self.log_level not in LOG_LEVELS:
            raise ValueError(f"Unsupported log level: {self.log_level}")
        if self.log_max_bytes < 1:
            raise ValueError("Log size must be positive")
        if self.log_backup_count < 1:
            raise ValueError("Log backup count must be positive")
