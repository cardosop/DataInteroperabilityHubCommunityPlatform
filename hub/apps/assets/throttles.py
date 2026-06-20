"""
Phase 250.1.A.10 — DRF throttles for ``POST /assets/data-first/``.

The fail-closed-at-intake re-sequence runs three external service
calls per request (S3 download + compliance + DQ). Without a rate
limit, a single misbehaving tenant or compromised user token can
saturate the worker pool and starve other tenants — see S-8 in the
preprod01 design doc.

Two throttle classes are layered:

* :class:`AssetDataFirstUserThrottle` — per-user 60 requests / min,
  read from ``DEFAULT_THROTTLE_RATES["asset_data_first_user"]``.
* :class:`AssetDataFirstTenantThrottle` — per-tenant 600 requests /
  min, read from ``DEFAULT_THROTTLE_RATES["asset_data_first_tenant"]``.

DRF cycles through every throttle in the view's ``throttle_classes``
list and the FIRST one to deny short-circuits the rest, so order
doesn't matter for correctness — both upper bounds are enforced.

The cache backend is the platform Redis backend (DRF's default
:class:`SimpleRateThrottle` reads from Django's default cache); no
extra config required as long as the platform's Django cache is
backed by Redis (which it is in staging + production per the helm
values).
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class AssetDataFirstUserThrottle(SimpleRateThrottle):
    """Per-user throttle for ``POST /assets/data-first/`` (60/min)."""

    scope = "asset_data_first_user"

    def get_cache_key(self, request, view) -> str | None:
        # Anonymous users never reach the endpoint (it's gated by
        # ``IsAuthenticated``); but DRF still calls the throttle on
        # every request, so we return None to skip the rate check
        # for unauthenticated requests rather than letting them
        # share a single bucket keyed on IP.
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class AssetDataFirstTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for ``POST /assets/data-first/`` (600/min).

    Resolves the tenant from the request via the same mechanism the
    view itself uses (:func:`hub.apps.tenants.request_tenant.get_request_tenant_id`)
    so a forged tenant context is impossible — DRF's middleware has
    already validated the user's tenant claim by the time the
    throttle runs.
    """

    scope = "asset_data_first_tenant"

    def get_cache_key(self, request, view) -> str | None:
        if not request.user or not request.user.is_authenticated:
            return None
        # Defer the import so the module doesn't pull tenants on
        # import (the throttle module is loaded by ``urls.py``
        # extremely early in the startup sequence).
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            # Without a tenant we can't bucket per-tenant; let the
            # per-user throttle handle the rate-limit decision.
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }
