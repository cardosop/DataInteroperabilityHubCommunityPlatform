"""Shared JSON output helper (P.5 CLI↔SDK consistency contract).

The SDK's list methods unwrap paginated envelopes — they return the
``results`` list, not the envelope.  The CLI's ``--format json`` output
MUST mirror that shape, or ``cli/tests/e2e/test_cli_sdk_consistency.py``
drifts (the CLI returned ``{count, has_next, results, ...}`` while the
SDK returned the bare list).

Command handlers that render a paginated list MUST route their JSON
branch through :func:`print_json_output`; single-object and non-paginated
payloads pass through unchanged.

W6.3 (oss-release-remediation) — the helper is now the ONLY sanctioned
JSON renderer: ``sort_keys=True`` (deterministic output),
``default=str`` (non-serializable values render instead of crashing),
and NaN/Infinity sanitize to JSON ``null`` (``json.dumps`` emits the
invalid tokens ``NaN``/``Infinity`` — not parseable by any strict JSON
consumer).
"""

from __future__ import annotations

import json
import math
from typing import Any

import click

_PAGINATION_KEYS = ("count", "has_next", "has_previous", "next", "previous")


def unwrap_json_payload(data: Any) -> Any:
    """Unwrap a paginated envelope to its ``results`` list.

    A dict is treated as an envelope ONLY when it carries both a
    ``results`` key and at least one pagination key — so a domain object
    that happens to have a ``results`` field (e.g. a scan report) is
    passed through untouched.
    """
    if (
        isinstance(data, dict)
        and "results" in data
        and any(key in data for key in _PAGINATION_KEYS)
    ):
        return data["results"]
    return data


def _json_safe(value: Any) -> Any:
    """Recursively map non-finite floats to ``None`` (JSON has no NaN)."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def print_json_output(data: Any) -> None:
    """Emit the CLI's ``--format json`` payload, envelope-unwrapped."""
    payload = _json_safe(unwrap_json_payload(data))
    click.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
