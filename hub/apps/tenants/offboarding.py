"""
W4.3 — provider-agnostic tenant offboarding sweeper registry.

The tenant hard-delete sweep must clean provider-owned estate rows that
block the tenant cascade (``on_delete=PROTECT``/RESTRICT FKs) or that
would survive it as bare-UUID garbage. Control-plane estate models are
PER-PROVIDER and may not be imported outside their app (CLAUDE.md
"Control-Plane Provider Boundary Contract") — so ``tenants`` cannot
import ``databricks_admin`` models directly. This module is the
inversion seam, same shape as the cost-recording seam
(``hub/apps/warehouses/cost_recording`` + ``register_cost_backend``):

* a provider app implements a sweeper callable
  ``fn(tenant_id: uuid.UUID) -> dict[str, int]`` that deletes its
  estate rows for the tenant and returns itemized counts;
* the provider app registers it from its ``AppConfig.ready()``;
* ``run_tenant_offboard_sweepers`` invokes every registered sweeper
  inside ``tenant_context(tenant_id)`` — mandatory: the delta-share
  tables carry strict RLS policies (no enable-GUC gate) AND
  ``FORCE ROW LEVEL SECURITY``, so an unarmed connection sees zero
  rows and the sweeper would silently delete nothing.

The registry is provider-agnostic by construction: a future Snowflake
estate registers its own sweeper the same way, and the sweep picks it
up without touching this module.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

_OFFBOARD_SWEEPERS: dict[str, Callable[[uuid.UUID], dict[str, int]]] = {}


def register_tenant_offboard_sweeper(
    key: str,
    sweeper: Callable[[uuid.UUID], dict[str, int]],
) -> None:
    """Register a provider offboarding sweeper (called from app ``ready()``).

    Duplicate registration for the same key is a programming error and
    raises — two providers silently overwriting each other's sweeper
    would leave estate rows behind.
    """
    if key in _OFFBOARD_SWEEPERS:
        raise RuntimeError(f"Tenant offboarding sweeper {key!r} is already registered")
    _OFFBOARD_SWEEPERS[key] = sweeper


def get_registered_tenant_offboard_sweepers() -> (
    dict[str, Callable[[uuid.UUID], dict[str, int]]]
):
    """Snapshot of the registered sweepers (read-only view for tests/ops)."""
    return dict(_OFFBOARD_SWEEPERS)


def run_tenant_offboard_sweepers(tenant_id: uuid.UUID | str) -> dict[str, Any]:
    """Run every registered sweeper for ``tenant_id`` inside
    ``tenant_context``.

    Returns ``{sweeper_key: {itemized counts}}``. A failing sweeper
    propagates — the sweep's caller treats the pre-sweep as part of the
    hard-delete transaction, so a failed offboard rolls the whole
    tenant hard-delete back (no half-erased estate).
    """
    from hub.apps.tenants.request_tenant import tenant_context

    results: dict[str, Any] = {}
    with tenant_context(str(tenant_id)):
        for key, sweeper in _OFFBOARD_SWEEPERS.items():
            results[key] = sweeper(uuid.UUID(str(tenant_id)))
    return results
