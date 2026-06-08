# Phase 260.5.C — File partial unique constraint on (tenant, name)
# WHERE status='ACTIVE'.
#
# Postgres translates this to a partial unique INDEX so the
# uniqueness gate only applies to ACTIVE rows. Non-ACTIVE rows
# (PENDING, UPLOADING, COMPLETED, FAILED, DELETING, DELETED) do not
# participate — a user re-uploading "report.csv" after deleting an
# old one is fine; a user creating two LIVE files with the same
# display name is not.
#
# No data migration needed — existing rows are checked at index-
# creation time. If the existing data ALREADY contains two ACTIVE
# rows with the same (tenant, name), the migration fails fast at
# index creation. That's the correct behaviour: the platform
# can't quietly admit a constraint that a row violates today; the
# operator must resolve the duplicate manually before deploying
# the constraint.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0006_file_deleting_transient_state_and_deleted_at"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="file",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "ACTIVE")),
                fields=("tenant", "name"),
                name="unique_active_filename_per_tenant",
            ),
        ),
    ]
