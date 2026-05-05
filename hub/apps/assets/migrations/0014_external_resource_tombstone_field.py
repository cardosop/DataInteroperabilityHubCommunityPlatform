"""
Phase 250.5.A.5 (D250.16) — external-resource tombstone fields.

Additive-only migration: adds two nullable columns + their index to
``external_resource_references`` so the consumer-side row can carry
the producer-tenant identity AND the soft-delete tombstone timestamp.

* ``source_tenant_id`` (UUID, nullable) — Hub Tenant.id of the
  federated source. NULL for non-Hub federations (public CKAN, etc.).
* ``source_tenant_deleted_at`` (timestamptz, nullable) — populated by
  the Tenant soft-delete signal at
  ``hub.apps.tenants.signals.tombstone_federated_resources_on_tenant_delete``.

The ``models.Index`` on ``source_tenant_deleted_at`` supports the
cleanup task that scans for rows whose 90-day grace window has expired
(``source_tenant_deleted_at + 90d < NOW()``).

Non-breaking: both columns are nullable. Back-fill on existing rows
is not required — the federation cascade only inspects the new
columns when the post-save signal fires for a soft-deleted tenant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0013_visibility_to_property"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalresourcereference",
            name="source_tenant_id",
            field=models.UUIDField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Phase 250.5.A.5 (D250.16) — Hub Tenant.id of the "
                    "federated source (NULL when source is non-Hub, "
                    "e.g. public CKAN). Drives the source-tenant "
                    "deletion tombstone cascade."
                ),
            ),
        ),
        migrations.AddField(
            model_name="externalresourcereference",
            name="source_tenant_deleted_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Phase 250.5.A.5 (D250.16) — set by the Tenant "
                    "soft-delete signal when ``source_tenant_id`` "
                    "matches the deleted tenant. The consumer-side "
                    "row stays queryable until this + 90 days; after "
                    "that, scheduled cleanup may hard-delete."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="externalresourcereference",
            index=models.Index(
                fields=["source_tenant_deleted_at"],
                name="err_src_deleted_at_idx",
            ),
        ),
    ]
