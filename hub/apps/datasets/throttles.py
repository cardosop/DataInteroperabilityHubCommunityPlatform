"""
Phase 260.4.E — abuse caps on the manual dataset refresh action.

The ``POST /datasets/{id}/refresh/`` endpoint downloads the dataset's
backing file from S3 + re-runs schema inference + emits an audit row
on EVERY attempt. A buggy UI loop or a malicious TENANT_ADMIN could
spam refreshes to burn S3 read budget AND flood the audit log. The
throttle caps prevent that without affecting normal usage:

* Per-user 10/min — a user clicking Refresh repeatedly is fine for
  the typical "wait a moment, retry" workflow but caps a stuck-loop
  bug at one inference per 6 seconds.
* Per-tenant 60/min — many tenant admins simultaneously hitting
  Refresh stays under the cap; a single stuck script burns a single
  user's budget without affecting the other admins.

Mirror the established :mod:`hub.apps.files.throttles` pattern:
``SimpleRateThrottle`` subclasses with a ``scope`` registered in
``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``. DRF runs every
declared throttle on the action and 429s with the maximum ``wait``
when any one denies (per the DRF throttle stack semantics).
"""
from __future__ import annotations
from typing import Optional

from rest_framework.throttling import SimpleRateThrottle


class DatasetRefreshUserThrottle(SimpleRateThrottle):
    """Per-user throttle for ``POST /datasets/{id}/refresh/`` (10/min)."""

    scope = "dataset_refresh_user"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class DatasetRefreshTenantThrottle(SimpleRateThrottle):
    """Per-tenant throttle for ``POST /datasets/{id}/refresh/`` (60/min)."""

    scope = "dataset_refresh_tenant"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }


class DatasetTenantThrottle(SimpleRateThrottle):
    """283.6.12 — Per-tenant throttle for DatasetViewSet (120/min).

    Cache key includes tenant_id per Phase 273 convention so tenant A's
    exhaustion never affects tenant B's quota.
    """

    scope = "dataset_tenant"

    def get_cache_key(self, request, view) -> Optional[str]:
        if not request.user or not request.user.is_authenticated:
            return None
        from hub.apps.tenants.request_tenant import get_request_tenant_id

        tenant_id = get_request_tenant_id(request)
        if not tenant_id:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(tenant_id),
        }
