"""
285.10.1.0.5 — Compliance feature-flag gate mixin.

Follows the canonical ``DQFeatureFlagMixin`` pattern. Gates compliance
ViewSets on the appropriate feature flags.

Scopes:
  - ``"basic"`` (default) — gate on ``compliance_fail_closed_enabled``.
  - ``"warehouse"`` — gate on ``compliance_fail_closed_enabled AND
    warehouse_compliance_enabled`` (conjunctive: base kills first).
"""
from __future__ import annotations
from typing import Optional, Tuple

from rest_framework import status
from rest_framework.response import Response

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import get_request_tenant

ERR_COMPLIANCE_DISABLED = "COMPLIANCE_DISABLED"
ERR_WAREHOUSE_COMPLIANCE_DISABLED = "WAREHOUSE_COMPLIANCE_DISABLED"


def _flag_disabled_response(error_code: str, message: str) -> Response:
    return Response(
        {"error_code": error_code, "detail": message},
        status=status.HTTP_403_FORBIDDEN,
    )


class _ComplianceFlagDeniedException(Exception):
    """Sentinel so handle_exception can return the canonical 403 shape."""

    def __init__(self, response: Response):
        self.response = response


def check_compliance_enabled(
    request,
) -> Tuple[Optional[Tenant], Optional[Response]]:
    """Return ``(tenant, None)`` when ``compliance_fail_closed_enabled``
    is on for the tenant.  Returns ``(None, 403)`` when the flag is off
    or no tenant context is available."""
    _tid, tenant = get_request_tenant(request)
    if tenant is None:
        return None, _flag_disabled_response(
            ERR_COMPLIANCE_DISABLED,
            "Tenant context required for compliance access.",
        )
    if not getattr(tenant, "compliance_fail_closed_enabled", False):
        return None, _flag_disabled_response(
            ERR_COMPLIANCE_DISABLED,
            "Compliance features are not enabled for this tenant.",
        )
    return tenant, None


def check_warehouse_compliance_enabled(
    request,
) -> Tuple[Optional[Tenant], Optional[Response]]:
    """285.10.1.0.5 — Return ``(tenant, None)`` when BOTH
    ``compliance_fail_closed_enabled`` AND ``warehouse_compliance_enabled``
    are on.  Conjunctive — the base wins when off."""
    tenant, denied = check_compliance_enabled(request)
    if denied is not None:
        return None, denied
    assert tenant is not None
    if not getattr(tenant, "warehouse_compliance_enabled", False):
        return None, _flag_disabled_response(
            ERR_WAREHOUSE_COMPLIANCE_DISABLED,
            "Warehouse-native compliance scans are not enabled for this tenant.",
        )
    return tenant, None


class ComplianceFeatureFlagMixin:
    """285.10.1.0.5 — Drop-in mixin that gates a ViewSet on
    compliance feature flag(s).

    Subclasses set ``compliance_flag_scope`` (class attribute):

    * ``"basic"`` (default) — gate on ``compliance_fail_closed_enabled``.
    * ``"warehouse"`` — gate on ``compliance_fail_closed_enabled AND
      warehouse_compliance_enabled``.
    """

    compliance_flag_scope: str = "basic"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.compliance_flag_scope == "warehouse":
            check_fn = check_warehouse_compliance_enabled
        else:
            check_fn = check_compliance_enabled
        _tenant, denied = check_fn(request)
        if denied is not None:
            raise _ComplianceFlagDeniedException(denied)

    def handle_exception(self, exc):
        if isinstance(exc, _ComplianceFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
