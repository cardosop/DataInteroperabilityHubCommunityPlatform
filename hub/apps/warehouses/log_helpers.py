"""
Phase 275.A.5 — PII-redaction extension for warehouse logging.

Extends the DQ log_helpers pattern with warehouse-specific sensitive keys.
Every ``logger.*(..., extra={...})`` call site in ``hub/apps/warehouses/``
MUST wrap payloads in ``_redact()``.
"""

from __future__ import annotations

from typing import Any

# Warehouse-specific sensitive keys (extended per 275.A.5).
_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "connection_string",
        "password",
        "account",
        "private_key",
        "service_account_json",
        "pat_token",
        "client_secret",
        "aws_secret_access_key",
        "config",
        "credentials",
        "token",
        "secret",
        "api_key",
    }
)


def _redact(obj: Any) -> Any:
    """Recursively strip sensitive keys from a logging payload.

    Borrowed from ``hub.apps.dq.log_helpers._redact()`` pattern.
    """
    if isinstance(obj, dict):
        return {k: "***REDACTED***" if k in _REDACTED_KEYS else _redact(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


def redact_extra(**extra: Any) -> dict[str, Any]:
    """Convenience: ``logger.info(..., extra=redact_extra(tenant_id=..., config=...))``."""
    return _redact(extra)
