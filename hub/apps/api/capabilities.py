"""
Phase 228 (REQ-LIN-006, 228.0.18) — capability-flag registry.

Capability flags are a backend-driven feature-discovery surface so the
frontend can branch its UI on what the deployed backend supports
without a separate config file or environment-variable shadow. The
endpoint lives at ``GET /api/v1/capabilities/`` and returns a flat
mapping of ``capability_name -> bool``.

Phase 228 ships five lineage capability flags:

* ``lineage.cross_tenant_marketplace`` — cross-tenant marketplace
  lineage browsing (Phase 228 F1).
* ``lineage.field_level_mapping`` — field-level lineage mapping editor
  (Phase 228 F2).
* ``lineage.change_notifications`` — lineage change-notification
  emails + in-app inbox (Phase 228 F3).
* ``lineage.openlineage_export`` — OpenLineage event-export adapter
  (Phase 228 F4).
* ``lineage.snapshots`` — lineage snapshot UI (Phase 228 F5).

Each flag defaults to ``False`` in production / staging. In the
``test`` environment ALL flags default to ``True`` so test fixtures
exercise the full feature surface without per-test setup. The
default policy is encoded in :func:`get_capabilities` so future
flags inherit the same shape.
"""
from __future__ import annotations

from typing import Dict

from django.conf import settings


# Phase 228 lineage capability flag names. The shared registry is the
# single source of truth for the five names — frontend
# ``useCapability('lineage.<flag>')`` keys against the same identifier.
LINEAGE_CAPABILITY_FLAGS: tuple[str, ...] = (
    "lineage.cross_tenant_marketplace",
    "lineage.field_level_mapping",
    "lineage.change_notifications",
    "lineage.openlineage_export",
    "lineage.snapshots",
)


def _is_test_environment() -> bool:
    """Test mode auto-enables every flag so fixtures exercise the full
    surface. Recognises ``ENVIRONMENT=test`` (canonical), ``DJANGO_ENV=test``
    (legacy), or pytest's own ``PYTEST_CURRENT_TEST`` env var (so any
    test-runner invocation defaults to ON regardless of how the env is set)."""
    import os
    if getattr(settings, "ENVIRONMENT", "").lower() == "test":
        return True
    if os.environ.get("DJANGO_ENV", "").lower() == "test":
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return False


def get_capabilities() -> Dict[str, bool]:
    """Return the flat capability map for the current environment.

    Default policy (REQ-LIN-006):

    * Production / staging: all flags ``False``.
    * Test: all flags ``True``.

    Per-flag overrides can be supplied via Django settings under the
    ``CAPABILITY_FLAGS`` dict (keyed by flag name). An override of
    ``True`` or ``False`` wins over the environment-driven default —
    that's the escape hatch ops uses to flip a flag on for a single
    customer or to roll-out gradually.
    """
    overrides: Dict[str, bool] = getattr(settings, "CAPABILITY_FLAGS", {}) or {}
    test_default = _is_test_environment()
    out: Dict[str, bool] = {}
    for name in LINEAGE_CAPABILITY_FLAGS:
        if name in overrides:
            out[name] = bool(overrides[name])
        else:
            out[name] = test_default
    return out


def is_capability_enabled(name: str) -> bool:
    """Check a single capability flag. Unknown names return ``False``."""
    return get_capabilities().get(name, False)


def is_capability_enabled_for_tenant(name: str, tenant_id: str | None) -> bool:
    """Phase 228 F5 (228.F5.DoD.6) — per-tenant rollout knob.

    Returns True iff EITHER the global flag is ON OR the tenant is in
    the per-flag allow-list. Lets ops phase a rollout 5 → 50% → 100%
    without code changes:

      - Phase 1 (canary, 5 internal tenants): set
        ``CAPABILITY_FLAGS_ROLLOUT_TENANTS = {"<flag>": ["<uuid>", ...]}``
        and keep the global flag OFF.
      - Phase 2 (50%): expand the allow-list.
      - Phase 3 (100% GA): set the global flag ON in
        ``CAPABILITY_FLAGS = {"<flag>": True}``; the per-tenant
        allow-list becomes redundant (still honored, no-op).

    Falls back to the global flag check when ``tenant_id`` is None,
    so existing call-sites that don't carry tenant context keep the
    same semantics.
    """
    if is_capability_enabled(name):
        return True
    if tenant_id is None:
        return False
    overrides = getattr(settings, "CAPABILITY_FLAGS_ROLLOUT_TENANTS", {}) or {}
    allow_list = overrides.get(name, ())
    if not allow_list:
        return False
    # Compare both as strings — settings may carry UUID-as-str.
    return str(tenant_id) in {str(x) for x in allow_list}


def get_capabilities_for_request(request) -> Dict[str, bool]:
    """Phase 240.4.B.4 — per-request capability map.

    Extends :func:`get_capabilities` with PER-TENANT capability values
    resolved from the authenticated user's tenant.  The SPA reads this
    response to render menus correctly without a separate
    "tenant features" endpoint round-trip.

    Currently exposes:

    * ``data_quality`` — mirror of ``Tenant.data_quality_enabled``
      (default True per D240.18).
    * ``data_quality_advanced`` — conjunctive
      ``Tenant.data_quality_enabled AND
      Tenant.data_quality_advanced_enabled``.  Conjunctive on the wire
      so the SPA never advertises a sub-feature whose parent is
      disabled — matches the backend gate semantics in
      ``check_data_quality_advanced_enabled``.

    Falls back to the global static map (``get_capabilities()``) when
    the request has no resolved tenant — anonymous + unauthenticated
    requests see only the lineage flags.
    """
    base = get_capabilities()

    tenant = None
    try:
        from hub.apps.tenants.request_tenant import get_request_tenant
        _tid, tenant = get_request_tenant(request)
    except Exception:  # noqa: BLE001 — capabilities must NEVER 500
        # If tenant resolution itself blows up (e.g. middleware not
        # in pipeline), degrade gracefully — anonymous capability
        # response is correct for an unauthenticated request.
        tenant = None

    dq_base = bool(getattr(tenant, "data_quality_enabled", True)) if tenant else False
    dq_advanced_flag = (
        bool(getattr(tenant, "data_quality_advanced_enabled", False))
        if tenant
        else False
    )
    base["data_quality"] = dq_base
    # Conjunctive on the wire so the SPA never sees
    # ``data_quality=False, data_quality_advanced=True`` — that would
    # mislead the menu-rendering code.
    base["data_quality_advanced"] = dq_base and dq_advanced_flag

    return base


__all__ = [
    "LINEAGE_CAPABILITY_FLAGS",
    "get_capabilities",
    "get_capabilities_for_request",
    "is_capability_enabled",
    "is_capability_enabled_for_tenant",
]
