"""
W4.3 / E2 — Delta Sharing estate offboarding sweeper.

``DeltaShareRecipient`` / ``DeltaShareToken`` / ``DeltaShareSnapshot``
carry ``on_delete=PROTECT`` against ``tenants.Tenant`` — pre-fix a tenant
that had ever used Delta Sharing could never be hard-deleted (the sweep
skipped it as ``cascade_failed`` forever, so the 90-day erasure contract
silently failed).

The sweeper deletes the estate rows itemized BEFORE the tenant cascade.
Registered into the provider-agnostic offboarding registry
(``hub.apps.tenants.offboarding``) from ``databricks_admin/apps.py`` —
the same provider-boundary inversion as the cost-recording seam:
``tenants`` never imports this module.

Deletion order:

1. snapshots — independent rows (no recipient FK); their Parquet files
   in Hub S3 die with the tenant's bucket prefix purge,
2. recipients — DB CASCADE removes their tokens,
3. residual tokens — defence-in-depth for any row whose recipient was
   already gone (counts 0 on a consistent estate).

The registry runner invokes this inside ``tenant_context(tenant_id)`` —
mandatory on the delta-share tables: strict RLS policy + ``FORCE ROW
LEVEL SECURITY`` means an unarmed DELETE matches zero rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid


def sweep_delta_share_estate(tenant_id: uuid.UUID | str) -> dict[str, int]:
    """Delete all Delta Sharing estate rows for ``tenant_id``.

    Returns ``{"snapshots": n, "recipients": n, "tokens": n}`` —
    itemized counts for the ``TENANT_HARD_DELETED`` audit.
    """
    from hub.apps.databricks_admin.models import (
        DeltaShareRecipient,
        DeltaShareSnapshot,
        DeltaShareToken,
    )

    counts: dict[str, int] = {}

    # Count BEFORE delete: ``queryset.delete()`` returns the TOTAL rows
    # removed, which for recipients INCLUDES their cascaded tokens —
    # itemized counts must attribute one row per model, not double-count
    # the cascade.
    snapshot_qs = DeltaShareSnapshot.objects.filter(tenant_id=tenant_id)
    counts["snapshots"] = snapshot_qs.count()
    snapshot_qs.delete()

    recipient_qs = DeltaShareRecipient.objects.filter(tenant_id=tenant_id)
    counts["recipients"] = recipient_qs.count()
    recipient_qs.delete()  # cascades their tokens

    # Any token row left here is an orphan from a prior partial delete —
    # sweep it too. Key is ``access_grants``: the audit PII redactor
    # blanks any key CONTAINING "token" as a substring, so a *token*
    # name would ship "[REDACTED]" instead of the count.
    token_qs = DeltaShareToken.objects.filter(tenant_id=tenant_id)
    counts["access_grants"] = token_qs.count()
    token_qs.delete()

    return counts
