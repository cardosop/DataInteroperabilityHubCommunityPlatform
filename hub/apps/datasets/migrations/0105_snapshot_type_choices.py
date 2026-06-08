# Phase 260.6.B — formalise ``DatasetSnapshot.snapshot_type``
# choices.
#
# Pre-260.6.B, the field was a free-form ``CharField(max_length=20)``
# with the supported values listed only in ``help_text``. The Python
# layer accepted any string; downstream consumers had no contract
# guarantee that the column held a recognised value. Phase 260.6.B
# introduces ``SnapshotType`` (TextChoices) to formalise the set:
#
#   * FULL                — full snapshot (default; existing behaviour)
#   * SCHEMA_ONLY         — schema + format only
#   * METADATA_ONLY       — version + tags + metadata only
#   * INCREMENTAL         — post-MVP placeholder; runtime raises
#                           NotImplementedError per the
#                           file-storage spec.
#
# This migration is PYTHON-ONLY: no DB-column-type change, no data
# migration. The existing ``snapshot_type`` rows already carry one
# of {FULL, SCHEMA_ONLY, METADATA_ONLY} (FULL is the historical
# default; SCHEMA_ONLY / METADATA_ONLY are explicit caller choices
# from ``time_travel.create_snapshot``). The ``AlterField`` updates
# the model's Python-side choices set so Forms / DRF serializers
# reject unknown values going forward; persisted rows are
# unaffected.
#
# No DB CHECK constraint is added because INCREMENTAL is a valid
# enum member (anticipated future state) — we forbid only at the
# create_snapshot helper layer (NotImplementedError). Adding a
# CHECK that accepts INCREMENTAL would conflict with the runtime
# raise; adding a CHECK that forbids INCREMENTAL would force a
# follow-up migration the day INCREMENTAL ships. Keeping the
# enforcement at the helper layer leaves the DB column open to
# future use.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0104_dataset_file_handle_purpose"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datasetsnapshot",
            name="snapshot_type",
            field=models.CharField(
                choices=[
                    ("FULL", "Full"),
                    ("SCHEMA_ONLY", "Schema only"),
                    ("METADATA_ONLY", "Metadata only"),
                    (
                        "INCREMENTAL",
                        "Incremental (post-MVP placeholder)",
                    ),
                ],
                default="FULL",
                help_text=(
                    "Phase 260.6.B — snapshot type: FULL / "
                    "SCHEMA_ONLY / METADATA_ONLY / INCREMENTAL "
                    "(the last is a post-MVP placeholder that "
                    "raises NotImplementedError at creation time; "
                    "see ``SnapshotType`` enum docstring and the "
                    "file-storage spec)."
                ),
                max_length=20,
            ),
        ),
    ]
