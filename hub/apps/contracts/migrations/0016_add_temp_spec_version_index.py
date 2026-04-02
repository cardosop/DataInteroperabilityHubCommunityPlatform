"""
Migration 0016 — Phase 26.12.1

Adds a temporary index on original_spec_version to speed up the
v3.1.0 backfill migration (0017) which filters
WHERE original_spec_version = '3.1.0'.

Without this index, the backfill becomes a sequential scan on
large tenants.  The index is dropped in migration 0018.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0015_normalise_regulation_keys"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="contract",
            index=models.Index(
                fields=["original_spec_version"],
                name="tmp_spec_ver_idx",
            ),
        ),
    ]
