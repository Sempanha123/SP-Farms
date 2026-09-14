import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

# Match tokens, passwords, cookies, authorization headers, 2FA secrets, and raw private keys
_REDACTION_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[^\s,;]+"),
    re.compile(
        r"(?i)((?:password|token|secret|cookie|recovery[_ -]?code|totp|seed)\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bEAAB[A-Za-z0-9]{20,}\b"),  # Facebook access tokens
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),  # JWT
)

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(password|secret|token|cookie|auth|credential|seed|key|signature|private)"
)


def redact_text(value: str) -> str:
    """Redact sensitive values such as tokens, passwords, and cookies from text."""
    if not value:
        return value
    redacted = value
    for pattern in _REDACTION_PATTERNS:
        replacement = r"\1[REDACTED]" if r"\1" in pattern.pattern else "[REDACTED]"
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_data(data: Any) -> Any:
    """Recursively scrub sensitive keys and string values in dictionary or list structures."""
    if isinstance(data, str):
        return redact_text(data)
    if isinstance(data, Mapping):
        scrubbed: dict[str, Any] = {}
        for k, v in data.items():
            key_str = str(k)
            if _SENSITIVE_KEY_PATTERN.search(key_str):
                scrubbed[key_str] = "[REDACTED]"
            else:
                scrubbed[key_str] = redact_data(v)
        return scrubbed
    if isinstance(data, Sequence) and not isinstance(data, (bytes, bytearray)):
        return [redact_data(item) for item in data]
    return data


def safe_json_dumps(data: Any, indent: int | None = None) -> str:
    """Safely dump JSON with recursive redaction applied."""
    scrubbed = redact_data(data)
    return json.dumps(scrubbed, ensure_ascii=False, indent=indent, default=str)
