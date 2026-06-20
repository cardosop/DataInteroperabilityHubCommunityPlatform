"""
Wire-shape helpers for GET …/compliance/runs/{id}/results/ only.

Keeps serializers honest (discovery badge can still fail closed on malformed
``regulation_mapping_json.regulation_summary``) while the results endpoint
exposes a stable list-or-null contract to the SPA.
"""

from __future__ import annotations

from typing import Any


def regulation_summaries_wire(regulation_mapping: dict[str, Any] | None) -> list[Any] | None:
    raw = (regulation_mapping or {}).get("regulation_summary")
    if raw is None:
        return None
    return raw if isinstance(raw, list) else None


def alert_dict_wire(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def legal_basis_violations_wire(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else []
