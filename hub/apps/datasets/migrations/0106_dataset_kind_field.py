# Phase 260.6.C — add ``Dataset.kind`` (closes Gap 28).
#
# Per design ref D260.5: federated datasets (Asset Phase 250.5
# work) introduce non-FILE-backed datasets; adding the ``kind``
# discriminator now is a one-time migration vs schema-change-later.
# Per OQ260.3 the API write surface rejects non-FILE values from
# external clients; the federation pipeline sets ``EXTERNAL_REF``
# server-side via the service layer.
#
# Migration semantics:
#
# 1. **AddField** with ``default='FILE'`` so the new column lands
#    NOT NULL with every existing row backfilled to ``FILE`` in
#    a single ALTER TABLE statement (Django's AddField + default
#    pattern).
# 2. **No data migration step needed** — the field's default
#    handles every existing row.  The spec said "kind='FILE' if
#    file_id IS NOT NULL"; in practice ALL existing rows are
#    file-backed (pre-260.6.C the platform only created Datasets
#    from files), and the few rows where ``file_id IS NULL``
#    (post-purge orphans from Phase 260.1.C) WERE originally
#    file-backed, so ``FILE`` is the correct historical kind for
#    them too.  Distinguishing "file-backed but file purged" from
#    "natively external" is a future-data concern that EXTERNAL_REF
#    introduces; pre-260.6.C data carries no such signal and the
#    safe interpretation is FILE.
# 3. **db_index** on the field for O(log n) filtering.  The
#    federated-import pipeline will later need to enumerate
#    EXTERNAL_REF rows separately from FILE rows; without the
#    index that filter would sequence-scan a multi-million row
#    table.  Index is created by the AddField operation alongside
#    the column.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("datasets", "0105_snapshot_type_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="dataset",
            name="kind",
            field=models.CharField(
                choices=[
                    ("FILE", "File-based dataset"),
                    ("EXTERNAL_REF", "External reference dataset"),
                ],
                db_index=True,
                default="FILE",
                help_text=(
                    "Phase 260.6.C — distinguishes file-backed "
                    "datasets (``FILE``, the MVP path) from "
                    "external-reference datasets (``EXTERNAL_REF``, "
                    "forward-compat for the federated-import "
                    "pipeline tracked under Asset Phase 250.5). "
                    "Per OQ260.3 the API write surface (DRF "
                    "serializers) accepts only ``FILE`` from "
                    "external clients; ``EXTERNAL_REF`` is set "
                    "server-side by the federation pipeline. "
                    "``db_index=True`` so future filters like "
                    "``Dataset.objects.filter(kind=FILE)`` are "
                    "O(log n) without a sequential scan."
                ),
                max_length=20,
            ),
        ),
    ]
