"""
Phase 228 X (REQ-LIN-X-004 / 228.X.4) — data residency enforcement.

Pure-function policy module: no DB access, no signal emission. The
view layer threads ``check_residency_allowed(...)`` into every
cross-tenant lineage read and either passes through OR returns the
spec-mandated 403 + audit row.

Decision matrix:

  | viewer.region | edge_owner.region | consent header | outcome     |
  |---------------|-------------------|----------------|-------------|
  | <any>         | NULL (legacy)     | <any>          | ALLOW       |
  | == owner      | <any>             | <any>          | ALLOW       |
  | != owner      | NOT NULL          | absent / false | BLOCK (403) |
  | != owner      | NOT NULL          | true           | ALLOW + audit|

The consent header is `X-Lineage-Cross-Region-Consent: true`; the
view-layer translator also accepts the form-encoded fallback for
non-browser clients.
"""

from __future__ import annotations

import enum
from typing import Any

CONSENT_HEADER = "HTTP_X_LINEAGE_CROSS_REGION_CONSENT"
"""Canonical Django META key for the consent header."""

CONSENT_QUERY_PARAM = "cross_region_consent"
"""Query-param fallback for non-browser clients."""

DATA_RESIDENCY_BLOCK_CODE = "DATA_RESIDENCY_BLOCK"
"""REQ-LIN-X-004 — error code surfaced in the 403 response body."""


class ResidencyOutcome(str, enum.Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ALLOW_WITH_CONSENT = "allow_with_consent"


def check_residency_allowed(
    *,
    viewer_region: str | None,
    owner_region: str | None,
    consent: bool,
) -> ResidencyOutcome:
    """Pure-function residency decision.

    Args:
        viewer_region: ``Tenant.data_residency_region`` of the
            request-side tenant. NULL = legacy (no rule).
        owner_region: residency region of the edge-owning tenant.
            NULL = legacy.
        consent: True iff the request carried the consent header.

    Returns:
        ``ResidencyOutcome`` — the caller maps ALLOW/ALLOW_WITH_CONSENT
        to a pass-through (with audit emission for the latter) and
        BLOCK to the 403 response.
    """
    # No residency policy on the owner → legacy behaviour, allow.
    if not owner_region:
        return ResidencyOutcome.ALLOW
    # Same region → in-residency, allow.
    if viewer_region and viewer_region == owner_region:
        return ResidencyOutcome.ALLOW
    # Cross-region — gated by consent.
    if consent:
        return ResidencyOutcome.ALLOW_WITH_CONSENT
    return ResidencyOutcome.BLOCK


def consent_from_request(request: Any) -> bool:
    """Read the consent signal from the request — header first, then
    query-param fallback. Pure-function for testability."""
    header_value = ""
    meta = getattr(request, "META", None) or {}
    if isinstance(meta, dict):
        header_value = str(meta.get(CONSENT_HEADER, "")).strip().lower()
    if header_value in ("1", "true", "yes"):
        return True
    qp = getattr(request, "query_params", None) or getattr(request, "GET", None)
    if qp is not None:
        try:
            qp_value = str(qp.get(CONSENT_QUERY_PARAM, "")).strip().lower()
        except Exception:
            qp_value = ""
        if qp_value in ("1", "true", "yes"):
            return True
    return False


__all__ = [
    "CONSENT_HEADER",
    "CONSENT_QUERY_PARAM",
    "DATA_RESIDENCY_BLOCK_CODE",
    "ResidencyOutcome",
    "check_residency_allowed",
    "consent_from_request",
]
