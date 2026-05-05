# Phase 250.5.F.2 (closes G2-4) — consumer-side soft-delete
# timestamp on ``ExternalResourceReference``.
#
# Adds ``ExternalResourceReference.deleted_at`` DateTimeField
# (nullable, db-indexed). Distinct semantics from the existing
# ``source_tenant_deleted_at`` field:
#
#   * source_tenant_deleted_at — source-side cascade signal
#     (set by the Tenant soft-delete signal when the source
#     tenant is deleted); 90-day grace window per D250.16
#     before scheduled cleanup hard-deletes.
#
#   * deleted_at (this migration) — consumer-side
#     user-initiated delete; the federated copy is hidden from
#     listing queries but retained for audit history (no
#     automatic hard-delete). The user can delete their
#     federated copy without affecting the source.
#
# Migration safety:
# * ``AddField`` with ``null=True`` + no default — PostgreSQL
#   adds the column without a row rewrite.
# * Index added in same operation; PostgreSQL builds the index
#   over an all-NULL column instantly (zero data).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0014_external_resource_tombstone_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalresourcereference",
            name="deleted_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Phase 250.5.F.2 — consumer-side soft-delete "
                    "timestamp. Independent of "
                    "``source_tenant_deleted_at``. When set, the "
                    "federated copy is hidden from consumer-side "
                    "list views but kept for audit history."
                ),
            ),
        ),
    ]
