"""
285.12.7.7 7G — Structlog RedactingProcessor.

Strips PII-bearing keys from structlog event dicts before emission.
"""
from __future__ import annotations
import re
from typing import Any

# Keys whose values should be redacted from log output.
_REDACTED_KEYS: frozenset[str] = frozenset({
    "email", "password", "token", "secret", "api_key",
    "credit_card", "ssn", "passport", "phone", "address",
    "authorization", "cookie", "session_id",
    "access_token", "refresh_token", "jwt",
})

# Regex patterns to redact from string values.
_REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Bearer\s+[^\s]+"), "Bearer [REDACTED]"),
    (re.compile(r"ApiKey\s+[^\s]+"), "ApiKey [REDACTED]"),
    (re.compile(r"[a-f0-9]{64}"), "[HASH_REDACTED]"),
]


def _redact_value(value: Any, key: str = "") -> Any:
    """Recursively redact PII from *value*."""
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if k in _REDACTED_KEYS else _redact_value(v, k)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(v, key) for v in value]
    if isinstance(value, str) and key in _REDACTED_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        for pattern, replacement in _REDACT_PATTERNS:
            value = pattern.sub(replacement, value)
    return value


class RedactingProcessor:
    """Structlog processor that redacts PII before emission."""

    def __call__(self, logger, method_name, event_dict):
        return _redact_value(event_dict)
