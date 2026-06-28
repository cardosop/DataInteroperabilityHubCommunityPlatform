"""
Common validation utilities for business rules.

Provides shared helper functions used across business rules implementations:
- ``get_field_path`` — traverse nested dictionaries by dotted-path
- ``validate_tenant_context`` — tenant-ID consistency check
- ``check_value_overlap`` — value overlap detection
- ``collect_errors`` — declarative error collection
- ``make_validation_result`` — convenience constructor for ValidationResult

These utilities were extracted from duplicated patterns found in 26 business_rules.py
files across the codebase (Phase 9.7.2). Individual apps can migrate their private
helpers to use these shared functions at their next maintenance touchpoint.
"""

from __future__ import annotations

from typing import Any

from hub.apps.core.business_rules.base import ValidationResult


def get_field_path(
    data: dict[str, Any],
    path: str,
    default: Any = None,
    *,
    separator: str = ".",
) -> Any:
    """Traverse a nested dictionary by dotted-path string.

    Example:
        >>> get_field_path({"a": {"b": {"c": 42}}}, "a.b.c")
        42
        >>> get_field_path({"a": {}}, "a.b.x", default=None)
        None
        >>> get_field_path({"a": 1}, "a.b", default="fallback")
        'fallback'

    Args:
        data: The nested dictionary to traverse.
        path: Dotted-path string (e.g. ``"info.owner.email"``).
        default: Value returned when a key is missing or an intermediate
            node is not a dict.
        separator: Path segment separator (default ``"."``).

    Returns:
        The value at *path*, or *default* if the path cannot be followed.
    """
    if not isinstance(data, dict):
        return default

    segments = path.split(separator)
    current: Any = data

    for segment in segments:
        if not isinstance(current, dict):
            return default
        try:
            current = current[segment]
        except KeyError:
            return default

    return current


def validate_tenant_context(
    expected_tenant_id: str | None,
    *entries: tuple[str, str | None],
) -> ValidationResult:
    """Check that one or more resources belong to the expected tenant.

    This is the canonical tenant-ID consistency check extracted from 15+
    ``_validate_tenant_context`` implementations across the codebase.

    Example:
        >>> result = validate_tenant_context(
        ...     "tenant-123",
        ...     ("dataset", "tenant-123"),
        ...     ("contract", "tenant-123"),
        ... )
        >>> result.is_valid
        True

        >>> result = validate_tenant_context(
        ...     "tenant-123",
        ...     ("dataset", "tenant-456"),
        ... )
        >>> result.is_valid
        False
        >>> result.errors[0]
        "dataset tenant (tenant-456) does not match expected tenant (tenant-123)"

    Args:
        expected_tenant_id: The tenant ID the calling rule is scoped to.
            If ``None``, the check returns valid with a warning about
            un-scoped execution (matching existing production behaviour).
        *entries: One or more ``(label, actual_tenant_id)`` pairs where
            *label* is a human-readable resource name and
            *actual_tenant_id* is the resource's tenant (or ``None`` if
            the resource has no tenant).

    Returns:
        ``ValidationResult`` with aggregated errors, warnings, and details.
    """
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"entries_checked": len(entries)}

    if expected_tenant_id is None:
        warnings.append(
            "validate_tenant_context called with no expected_tenant_id "
            "— tenant scoping is not enforced for this check"
        )
        return ValidationResult(
            is_valid=True, errors=errors, warnings=warnings, details=details
        )

    expected = str(expected_tenant_id)

    for label, actual in entries:
        if actual is None:
            errors.append(f"{label} has no tenant")
            details[label] = {"expected": expected, "actual": None}
            continue

        actual_str = str(actual)
        if actual_str != expected:
            errors.append(
                f"{label} tenant ({actual_str}) does not match "
                f"expected tenant ({expected})"
            )
            details[label] = {"expected": expected, "actual": actual_str}
        else:
            details[label] = "match"

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        details=details,
    )


def check_value_overlap(value1: Any, value2: Any) -> dict[str, Any]:
    """Detect overlap between two access-policy or permission values.

    Extracted from the byte-for-byte identical implementations in
    ``governance/business_rules.py`` and ``mesh/business_rules.py``.

    Handles:
    - **List intersection**: both values are lists → set intersection
    - **Value-in-list**: one list, one scalar → membership test
    - **Nested dicts**: both are dicts → reports type so the caller can
      dispatch a recursive check
    - **Exact match**: equal scalars
    - **No match**: none of the above

    Args:
        value1: First value to compare.
        value2: Second value to compare.

    Returns:
        Dict with keys ``"overlaps"`` (bool), ``"type"`` (str), and
        type-specific details (``"overlap_values"`` for list intersection,
        ``"nested_details"`` for dict comparison).
    """
    # Both lists — compute set intersection
    if isinstance(value1, list) and isinstance(value2, list):
        overlap_values = [v for v in value1 if v in value2]
        return {
            "overlaps": len(overlap_values) > 0,
            "type": "LIST_INTERSECTION",
            "overlap_values": overlap_values,
        }

    # One list, one scalar — membership test
    if isinstance(value1, list):
        return {
            "overlaps": value2 in value1,
            "type": "VALUE_IN_LIST",
        }
    if isinstance(value2, list):
        return {
            "overlaps": value1 in value2,
            "type": "VALUE_IN_LIST",
        }

    # Both dicts — report type for caller to dispatch recursive check
    if isinstance(value1, dict) and isinstance(value2, dict):
        return {
            "overlaps": False,
            "type": "NESTED_DICT",
            "nested_details": {"overlaps": False},
        }

    # Scalar equality
    if value1 == value2:
        return {"overlaps": True, "type": "EXACT_MATCH"}

    return {"overlaps": False, "type": "NO_MATCH"}


def collect_errors(*checks: tuple[bool, str]) -> list[str]:
    """Collect error messages for conditions that failed.

    Turns repeated ``if not x: errors.append(msg)`` blocks into a
    declarative list:

        errors = collect_errors(
            (dataset.tenant is not None, "Dataset must have a tenant"),
            (len(name) <= 255, f"Name too long: {len(name)}"),
        )

    Args:
        *checks: Pairs of ``(condition_passed, error_message)``.
            The message is included in the result only when
            *condition_passed* is ``False``.

    Returns:
        List of error messages for conditions that did not pass.
    """
    return [msg for passed, msg in checks if not passed]


def make_validation_result(
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> ValidationResult:
    """Create a ``ValidationResult`` with ``is_valid`` derived from errors.

    Convenience constructor that eliminates the boilerplate of computing
    ``is_valid = len(errors) == 0`` in every ``_validate_*`` method.

    Example:
        >>> vr = make_validation_result(
        ...     errors=["field X is required"],
        ...     warnings=["field Y is deprecated"],
        ... )
        >>> vr.is_valid
        False
        >>> vr.errors
        ['field X is required']

    Args:
        errors: List of error messages (default empty).
        warnings: List of warning messages (default empty).
        details: Additional detail dict (default empty).

    Returns:
        ``ValidationResult`` with ``is_valid`` set to ``len(errors) == 0``.
    """
    _errors = errors or []
    return ValidationResult(
        is_valid=len(_errors) == 0,
        errors=_errors,
        warnings=warnings or [],
        details=details or {},
    )
