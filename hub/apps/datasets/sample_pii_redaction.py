"""
Phase 260.3.E — server-side PII redaction for dataset sample rows.

Uses :func:`hub.apps.audit.utils._sanitize` for Phase-19-aligned control-character /
line-break neutralisation on string leaves, then replaces values that contain PII
patterns (email, phone, card, SSN) or bear high-risk column names with the literal
``[redacted]`` token returned by :func:`GET /datasets/{id}/sample/`.
"""

from __future__ import annotations
import re
from copy import deepcopy
from typing import Any

from hub.apps.audit.utils import _sanitize

SAMPLE_PII_REPLACEMENT = "[redacted]"

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\+?\d{10,15}\b")
_CARD_RE = re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# Mirrors ``redact_pii`` sensitive key hints in hub.apps.audit.utils (subset focused on tabular PII).
_NAME_HINT_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "password",
        "password_hash",
        "api_key",
        "token",
        "secret",
        "ssn",
        "social_security",
        "credit_card",
        "creditcard",
        "pan",
        "national_id",
        "passport",
        "drivers_license",
        "iban",
    }
)


def _column_name_suggests_pii(field_name: str) -> bool:
    key = field_name.lower()
    return any(h in key for h in _NAME_HINT_SUBSTRINGS)


def _scalar_string_contains_pii_pattern(value: str) -> bool:
    """True when scrubbed text still matches Phase-19-style PII patterns."""
    scrubbed = _sanitize(value)
    probe = _UUID_RE.sub("__UUID__", scrubbed)
    if _EMAIL_RE.search(probe):
        return True
    if _PHONE_RE.search(probe):
        return True
    if _CARD_RE.search(probe):
        return True
    if _SSN_RE.search(probe):
        return True
    return False


def redact_sample_cell(field_name: str, value: Any) -> Any:
    """
    Redact a single sample cell.

    The column-name hint check (e.g. ``ssn``, ``credit_card``, ``password``)
    runs BEFORE the value-type branch so that integer-typed PII columns
    (``{"ssn": 123456789}``) are masked too — relying solely on
    ``isinstance(value, str)`` would silently leak those.

    For string values, after a sanitisation pass we additionally
    pattern-match for email / phone / card / SSN even when the column
    name itself isn't a hint.

    ``None`` and other non-string scalars in non-sensitive columns pass
    through unchanged so numeric IDs, counts, booleans, etc. survive.
    """
    if value is None:
        return value
    if _column_name_suggests_pii(field_name):
        return SAMPLE_PII_REPLACEMENT
    if isinstance(value, str):
        if _scalar_string_contains_pii_pattern(value):
            return SAMPLE_PII_REPLACEMENT
        return _sanitize(value)
    return value


def redact_sample_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deep-copy each row dict and redact PII-bearing scalars."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fresh = deepcopy(row)
        out.append({k: redact_sample_cell(str(k), v) for k, v in fresh.items()})
    return out
