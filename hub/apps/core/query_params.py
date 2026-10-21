"""Canonical query-parameter parsing helpers (W11.11).

The DAST scans found the unvalidated ``int(request.query_params.get(...))``
pattern across five views — a fuzzed value (``10;``, ``;``) raised an
uncaught ``ValueError`` and 500'd.  Every integer query parameter must go
through :func:`parse_int_query_param` instead: invalid input is a typed
DRF ``ValidationError`` (the API's 400 VALIDATION_ERROR envelope), never
a 500.
"""

from __future__ import annotations

from rest_framework.exceptions import ValidationError


def parse_int_query_param(
    request,
    name: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Parse ``name`` from ``request.query_params`` as an integer.

    Returns ``default`` when the parameter is absent; raises the typed
    ``ValidationError`` on non-integer values (400 envelope) and on
    values outside ``min_value``/``max_value`` when bounds are given.
    """
    raw = request.query_params.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: "Must be a valid integer."}) from None
    if min_value is not None and value < min_value:
        raise ValidationError({name: f"Must be at least {min_value}."})
    if max_value is not None and value > max_value:
        raise ValidationError({name: f"Must be at most {max_value}."})
    return value


def parse_uuid_query_param(request, name: str, required: bool = False):
    """Parse ``name`` from ``request.query_params`` as a UUID.

    Returns None when the parameter is absent (or when ``required`` is
    True raises the typed ``ValidationError``).  Raises the typed
    ``ValidationError`` on non-UUID values — the DAST scans found the
    raw-string-to-ORM-filter class, where an invalid UUID escaped as a
    500 (``"dataset_id" is not a valid UUID`` with http_status 500).
    """
    import uuid as _uuid

    raw = request.query_params.get(name)
    if raw is None or raw == "":
        if required:
            raise ValidationError({name: "This field is required."})
        return None
    try:
        return str(_uuid.UUID(raw))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({name: f"Must be a valid UUID."}) from None
