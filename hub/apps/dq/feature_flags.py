"""
Phase 240.4.B.2 — DQ feature-flag gate helpers.

The two-flag conjunctive contract (per Tenant):

* ``Tenant.data_quality_enabled`` (default True) is the BASE kill-
  switch — when False, ALL DQ API endpoints (DQRunViewSet,
  DQAlertingRuleViewSet, DQQualityViewSet) return HTTP 403 +
  ``error_code: DATA_QUALITY_DISABLED`` regardless of role.
* ``Tenant.data_quality_advanced_enabled`` (default False)
  ADDITIONALLY gates the Phase 240.3.B advanced endpoints.  The base
  flag must ALSO be True for the advanced surface to work — i.e. the
  gate is conjunctive ``data_quality_enabled AND
  data_quality_advanced_enabled``; an off base flag wins (the response
  carries ``DATA_QUALITY_DISABLED`` rather than
  ``DATA_QUALITY_ADVANCED_DISABLED``).

Helpers:

* ``check_data_quality_enabled(request)`` — returns the resolved
  Tenant on success; returns a 403 ``Response`` on failure.  Use at
  the top of every basic-DQ-view dispatch (DQRunViewSet,
  DQAlertingRuleViewSet).
* ``check_data_quality_advanced_enabled(request)`` — returns the
  resolved Tenant on success; returns a 403 ``Response`` on failure.
  Use at the top of every advanced-DQ-view dispatch (DQQualityViewSet
  ``@action`` methods).

Both helpers return the canonical 403 shape per the spec wording for
240.4.B.2: ``{"error_code": "DATA_QUALITY_DISABLED"}`` (NOT the
standard ``api_error_response`` shape — the spec explicitly mandates
``error_code`` so client-side flag-aware UI can branch reliably).
"""
from __future__ import annotations

from typing import Optional, Tuple

from rest_framework import status
from rest_framework.response import Response

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import get_request_tenant


# Sentinel error_code values exposed on the 403 wire.  Test suite
# imports these so a future rename surfaces in CI.
ERR_DATA_QUALITY_DISABLED = "DATA_QUALITY_DISABLED"
ERR_DATA_QUALITY_ADVANCED_DISABLED = "DATA_QUALITY_ADVANCED_DISABLED"


def _flag_disabled_response(error_code: str, message: str) -> Response:
    """Construct the canonical 403 response shape mandated by 240.4.B.2.

    Uses ``error_code`` (NOT ``code``) at the top-level — the spec
    wording explicitly says ``{"error_code": "DATA_QUALITY_DISABLED"}``
    so SPA flag-aware UI can branch on a stable key.
    """
    return Response(
        {
            "error_code": error_code,
            "detail": message,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def check_data_quality_enabled(request) -> Tuple[Optional[Tenant], Optional[Response]]:
    """Return ``(tenant, None)`` when the BASE DQ flag is on.

    Returns ``(None, response_403)`` when:
    * the request has no resolved tenant, OR
    * ``tenant.data_quality_enabled`` is False.

    Callers MUST short-circuit on the response side of the tuple.
    """
    _tid, tenant = get_request_tenant(request)
    if tenant is None:
        return None, _flag_disabled_response(
            ERR_DATA_QUALITY_DISABLED,
            "Tenant context required for DQ access.",
        )
    if not getattr(tenant, "data_quality_enabled", True):
        return None, _flag_disabled_response(
            ERR_DATA_QUALITY_DISABLED,
            "Data Quality is disabled for this tenant.",
        )
    return tenant, None


def check_data_quality_advanced_enabled(
    request,
) -> Tuple[Optional[Tenant], Optional[Response]]:
    """Return ``(tenant, None)`` when BOTH the base AND advanced flags
    are on.  Conjunctive — the base flag wins when off.

    Returns ``(None, response_403)`` with:
    * ``error_code=DATA_QUALITY_DISABLED`` when the base flag is off
      (regardless of the advanced flag value);
    * ``error_code=DATA_QUALITY_ADVANCED_DISABLED`` when the base flag
      is on but advanced is off.

    Callers MUST short-circuit on the response side of the tuple.
    """
    tenant, denied = check_data_quality_enabled(request)
    if denied is not None:
        return None, denied
    assert tenant is not None  # narrow for type-checker
    if not getattr(tenant, "data_quality_advanced_enabled", False):
        return None, _flag_disabled_response(
            ERR_DATA_QUALITY_ADVANCED_DISABLED,
            "Advanced Data Quality features are not enabled for this tenant.",
        )
    return tenant, None


# ─────────────────────────────────────────────────────────────────────
# ViewSet mixin — gates an entire ViewSet on the tenant flag(s).
# ─────────────────────────────────────────────────────────────────────


class _DQFlagDeniedException(Exception):
    """Sentinel exception raised from ``initial()`` when a DQ flag
    gate denies access.  Carries the canonical 403 ``Response`` so
    ``handle_exception`` can return it verbatim — bypassing the
    global ``custom_exception_handler`` whose envelope shape
    (``{"error": {"code": ..., ...}}``) does NOT match the
    spec-mandated wire shape (``{"error_code": ..., "detail": ...}``)
    for 240.4.B.2.
    """

    def __init__(self, response: Response):
        self.response = response


class DQFeatureFlagMixin:
    """Phase 240.4.B.2 — drop-in mixin that gates a ViewSet on the
    DQ feature flag(s).

    Subclasses set ``dq_flag_scope`` (class attribute):

    * ``"basic"`` (default) — gate on ``data_quality_enabled``.  Use
      for DQRunViewSet / DQAlertingRuleViewSet.
    * ``"advanced"`` — gate on the conjunctive
      ``data_quality_enabled AND data_quality_advanced_enabled``.
      Use for DQQualityViewSet (the four advanced endpoints
      anomalies / trends / scorecards / root_cause_analysis).

    The check fires from ``initial()`` AFTER DRF auth /
    permission / throttle checks (so the response codes are
    auth-correct: a missing token → 401, valid token but flag off →
    403).  Denials are raised as a sentinel exception that
    ``handle_exception`` translates into the canonical 403 wire
    shape.
    """

    dq_flag_scope: str = "basic"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.dq_flag_scope == "advanced":
            check_fn = check_data_quality_advanced_enabled
        else:
            check_fn = check_data_quality_enabled
        _tenant, denied = check_fn(request)
        if denied is not None:
            raise _DQFlagDeniedException(denied)

    def handle_exception(self, exc):
        if isinstance(exc, _DQFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
