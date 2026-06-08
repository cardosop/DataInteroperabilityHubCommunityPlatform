# Phase 260.5.A — Dataset.file_handle_purpose distinguisher.
#
# Adds the new CharField with choices (primary / sample / schema_only)
# defaulting to "primary" so existing rows backfill cleanly without a
# data-migration step (Django applies the field default on the ALTER
# TABLE that adds the column).
#
# AddConstraint enforces ``UNIQUE(tenant, file, file_handle_purpose)``
# WHERE ``file IS NOT NULL`` — Postgres partial-unique-index. This
# rejects concurrent attempts to insert two ``PRIMARY`` rows for the
# same file (the load-bearing invariant for 260.5.A.4) while still
# allowing PRIMARY + SAMPLE coexistence.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0103_backfill_retired_null_file_datasets"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
            name="file_handle_purpose",
            field=models.CharField(
                choices=[
                    ("primary", "Primary"),
                    ("sample", "Sample"),
                    ("schema_only", "Schema only"),
                ],
                db_index=True,
                default="primary",
                help_text=(
                    "Phase 260.5.A — disambiguates concurrent Dataset rows "
                    "backed by the same File. The (tenant, file, "
                    "file_handle_purpose) unique constraint (when file is "
                    "non-null) lets a tenant have AT MOST ONE PRIMARY + AT "
                    "MOST ONE SAMPLE + AT MOST ONE SCHEMA_ONLY dataset per "
                    "file — concurrent attempts to create a second PRIMARY "
                    "for the same file get 409, but PRIMARY + SAMPLE "
                    "coexist."
                ),
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="dataset",
            constraint=models.UniqueConstraint(
                condition=models.Q(("file__isnull", False)),
                fields=("tenant", "file", "file_handle_purpose"),
                name="unique_dataset_file_purpose_per_tenant",
            ),
        ),
    ]
