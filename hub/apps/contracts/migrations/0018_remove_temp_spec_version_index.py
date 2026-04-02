"""
Migration 0018 — Phase 26.12.3

Drops the temporary index on original_spec_version added in
0016 for the v3.1.0 backfill.  This index is no longer needed
after the backfill completes.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0017_hubcontract_v3_1_0_backfill"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="contract",
            name="tmp_spec_ver_idx",
        ),
    ]
