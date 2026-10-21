"""
Phase 227 Wave 1 (227.L6.4) — reverse migration for the
``ASSET_AUTO_REVERTED_STRUCTURELESS`` action emitted by
``renormalize_contracts --apply-asset-revert``.

Why a Django data migration rather than a management command
------------------------------------------------------------
We want the un-revert step to be:
1. **Pinned to a deployment** (a migration's forward semantics run
   exactly once per `migrate` to that revision).
2. **Reversible** (`migrate contracts <prev>` runs the migration's
   ``reverse_code`` callable — re-applies the revert so the team can
   roll back if a customer-action cohort wasn't ready for restoration).
3. **CI-testable** (Django's ``call_command("migrate")`` path is what
   other tests exercise, so this slots in cleanly).

Forward operation
-----------------
For every asset currently in ``DRAFT`` status that has an
``ASSET_AUTO_REVERTED_STRUCTURELESS`` audit event in its history,
restore the asset to the most-recently-recorded ``previous_status``.
Emits a paired ``ASSET_RESTORED_STRUCTURELESS`` event so the reverse
callable knows what to undo.

Reverse operation
-----------------
For every asset that has an ``ASSET_RESTORED_STRUCTURELESS`` event in
its history AND is currently NOT in ``DRAFT``, re-apply the demotion
(set asset to ``DRAFT``). Emits a new
``ASSET_AUTO_REVERTED_STRUCTURELESS`` event marking the replay so the
forward callable can run again (matching is by current asset state,
not event-pair tracking).

Audit-event invariants honored
------------------------------
* ``AuditEvent`` is append-only (the model overrides ``delete()`` to
  raise). Both directions of this migration ONLY create new events;
  no event is deleted or modified. Identity holds because the asset's
  current ``status`` field — not event presence/absence — gates the
  next operation.
* ``details_json`` (not ``details``) is the JSONField name on
  ``AuditEvent``; ``timestamp`` (not ``created_at``) is the
  auto-now-add field. Both are honored below.

Identity guarantee
------------------
Asset starts at status S. An ``--apply-asset-revert`` run demoted it
S → DRAFT. Forward of THIS migration: DRAFT → S. Reverse of THIS
migration: S → DRAFT. So ``forward(reverse(state)) == state`` for any
state in the (S, DRAFT) cohort. The L6.6 CI test pins this property
end-to-end.
"""

from django.db import migrations
from django.utils import timezone


def _previous_status_from_event(event) -> str | None:
    """Pull ``previous_status`` from an audit-event ``details_json`` dict."""
    details = event.details_json
    if not isinstance(details, dict):
        return None
    return details.get("previous_status")


def _restore_assets(apps, schema_editor):
    """Forward — restore assets that were demoted by Phase 227 self-heal.

    Looks at each asset currently in ``DRAFT`` status that has at least
    one ``ASSET_AUTO_REVERTED_STRUCTURELESS`` event in its history.
    Restores the asset to the ``previous_status`` recorded in the most
    recent such event. Emits a paired ``ASSET_RESTORED_STRUCTURELESS``
    event so the reverse callable has a deterministic record of what
    THIS migration did.
    """
    AuditEvent = apps.get_model("audit", "AuditEvent")
    Asset = apps.get_model("assets", "Asset")

    # Find all distinct resource_ids that have a revert event.
    revert_resource_ids = set(
        AuditEvent.objects.filter(
            action="ASSET_AUTO_REVERTED_STRUCTURELESS",
            resource_id__isnull=False,
        ).values_list("resource_id", flat=True)
    )
    if not revert_resource_ids:
        return

    for asset_id in revert_resource_ids:
        asset = Asset.objects.filter(id=asset_id).first()
        if asset is None:
            # Asset was deleted since the revert — skip silently.
            continue
        if asset.status != "DRAFT":
            # Operator manually restored, never demoted, or already
            # restored by an earlier migration run — skip.
            continue
        # Most recent revert event wins (latest timestamp).
        latest_revert = (
            AuditEvent.objects.filter(
                action="ASSET_AUTO_REVERTED_STRUCTURELESS",
                resource_id=asset_id,
            )
            .order_by("-timestamp")
            .first()
        )
        if latest_revert is None:
            continue
        previous_status = _previous_status_from_event(latest_revert)
        if previous_status not in {"ACTIVE", "PUBLIC"}:
            # Defensive: don't restore to an unrecognised status. The
            # only legitimate pre-revert states are ACTIVE and PUBLIC
            # (the apply command demotes from those).
            continue

        asset.status = previous_status
        asset.updated_at = timezone.now()
        asset.save(update_fields=["status", "updated_at"])

        AuditEvent.objects.create(
            tenant=getattr(asset, "tenant", None),
            actor_user=None,
            resource_type="ASSET",
            resource_id=asset_id,
            action="ASSET_RESTORED_STRUCTURELESS",
            result="SUCCESS",
            details_json={
                "previous_status": "DRAFT",
                "new_status": previous_status,
                "source_event_id": str(latest_revert.id),
                "migration": "0024_unrevert_structureless_assets",
            },
        )


def _redo_reverts(apps, schema_editor):
    """Reverse — re-apply the demotion this migration's forward undid.

    For each asset currently NOT in ``DRAFT`` that has an
    ``ASSET_RESTORED_STRUCTURELESS`` event in its history, demote it
    back to ``DRAFT``. Emits a new
    ``ASSET_AUTO_REVERTED_STRUCTURELESS`` event so a future forward
    run sees a fresh revert.

    No events are deleted (``AuditEvent`` is append-only); the asset's
    current status is the gate, not event presence.
    """
    AuditEvent = apps.get_model("audit", "AuditEvent")
    Asset = apps.get_model("assets", "Asset")

    restored_resource_ids = set(
        AuditEvent.objects.filter(
            action="ASSET_RESTORED_STRUCTURELESS",
            resource_id__isnull=False,
        ).values_list("resource_id", flat=True)
    )
    if not restored_resource_ids:
        return

    for asset_id in restored_resource_ids:
        asset = Asset.objects.filter(id=asset_id).first()
        if asset is None:
            continue
        if asset.status == "DRAFT":
            # Already at the target state.
            continue

        previous_status = asset.status
        asset.status = "DRAFT"
        asset.updated_at = timezone.now()
        asset.save(update_fields=["status", "updated_at"])

        AuditEvent.objects.create(
            tenant=getattr(asset, "tenant", None),
            actor_user=None,
            resource_type="ASSET",
            resource_id=asset_id,
            action="ASSET_AUTO_REVERTED_STRUCTURELESS",
            result="SUCCESS",
            details_json={
                "previous_status": previous_status,
                "new_status": "DRAFT",
                "replayed_from_migration": (
                    "0024_unrevert_structureless_assets"
                ),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0023_migration_checkpoint"),
        # Audit events are read inside RunPython — depend on the
        # latest audit migration so the AuditEvent model is in scope.
        ("audit", "0001_initial"),
        ("assets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            _restore_assets,
            reverse_code=_redo_reverts,
        ),
    ]
