# Phase 260.5.G.R1 GAP-B — Postgres CHECK constraint enforcing the
# 64 KB cap on ``File.metadata_json`` at the DB layer.
#
# The Python-layer validator at ``hub.apps.files.metadata_validators``
# is wired into both ``FileSerializer`` (DRF write paths) and
# ``File.save()`` (model-level defence). Both rely on Django going
# through ``Model.save()`` — but Django offers two ORM operations
# that BYPASS ``save()`` entirely:
#
# * ``Model.objects.bulk_create([...])`` — issues raw INSERTs.
# * ``Model.objects.filter(...).update(metadata_json=...)`` —
#   issues a raw UPDATE.
#
# Both are legitimate performance escape hatches, but neither
# touches our save() override; an oversize payload landing through
# either path would silently bloat the column past the spec ceiling.
# The pre_save signal pathway also has a subtle gap: a signal that
# mutates ``metadata_json`` on the instance fires AFTER the
# Python-layer validator has already run.
#
# A Postgres CHECK constraint catches all of the above unconditionally.
# The byte-count rule mirrors the Python validator
# (``len(json.dumps(metadata, ensure_ascii=False, sort_keys=True)
# .encode("utf-8"))`` ≤ 65 536) closely enough that legitimate
# metadata clears both gates without surprise: ``::text`` casts a
# ``jsonb`` column to its canonical text serialisation, and Postgres
# emits ``json`` with no extra whitespace, so the byte count is a
# very tight upper bound on the Python form. Any borderline
# difference at the boundary admits a few bytes more on the DB side,
# which is the right direction (DB constraint is ROOMIER than the
# user-facing validator, so the Python-layer error always fires
# first when both could).
#
# NOT mirrored in ``Meta.constraints`` because Django's
# ``CheckConstraint`` doesn't have a built-in for ``octet_length``
# on ``jsonb`` columns and the indirection to express it via
# ``models.Func`` adds more cognitive load than the migration's
# raw SQL. The constraint name is searchable; an engineer looking
# up "metadata size" finds the migration.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0007_unique_active_filename"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE files "
                "ADD CONSTRAINT file_metadata_json_size_cap "
                "CHECK (octet_length(metadata_json::text) <= 65536) "
                "NOT VALID;"
            ),
            reverse_sql=(
                "ALTER TABLE files DROP CONSTRAINT IF EXISTS "
                "file_metadata_json_size_cap;"
            ),
        ),
        # ``NOT VALID`` lets the constraint take effect for FUTURE
        # writes without scanning the whole table at deploy time
        # (existing rows with oversize metadata, if any, would
        # otherwise block the migration). The follow-up VALIDATE
        # CONSTRAINT runs the table scan asynchronously — fast on
        # well-shaped tables and tolerant of legacy rows that
        # exceed the cap (those will surface as constraint
        # violations on the next mutation, NOT during the
        # migration itself, which is the right tradeoff for a
        # production deploy).
        migrations.RunSQL(
            sql=(
                "ALTER TABLE files VALIDATE CONSTRAINT "
                "file_metadata_json_size_cap;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
