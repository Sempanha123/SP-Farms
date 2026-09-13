import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sp_farms.application.config import AppConfig

_REDACTION_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(r"(?i)((?:password|token|secret|cookie|recovery[_ -]?code)\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
)


def redact(value: str) -> str:
    redacted = value
    for pattern in _REDACTION_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(config: AppConfig) -> RotatingFileHandler:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        config.log_path,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger("sp_farms")
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(config.log_level)
    root.propagate = False
    return handler


def get_logger(module: str) -> logging.Logger:
    return logging.getLogger(f"sp_farms.{module}")


def read_redacted_log(path: Path) -> str:
    if not path.exists():
        return ""
    return redact(path.read_text(encoding="utf-8", errors="replace"))
