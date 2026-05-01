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


__all__ = [
    "LINEAGE_CAPABILITY_FLAGS",
    "get_capabilities",
    "is_capability_enabled",
    "is_capability_enabled_for_tenant",
]
