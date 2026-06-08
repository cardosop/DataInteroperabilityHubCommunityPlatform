"""Phase 234.6.1 — Postgres FTS index column on ``audit_events``.

Adds a STORED ``GENERATED ALWAYS AS (...)`` tsvector column the
search-list endpoint consults via ``@@ websearch_to_tsquery(...)``. The
GENERATED expression composes three sources with weighted lexemes so
``ts_rank`` ordering reflects intent:

* ``action``         → weight 'A' (highest — direct field match)
* ``resource_type``  → weight 'B'
* ``details_json``   → weight 'C' (via ``jsonb_to_tsvector('english',
                       …, '"all"')`` so both keys AND values index)

The expression also runs ``translate(.., '_', ' ')`` on ``action`` /
``resource_type`` so Postgres's default English parser splits
``ASSET_CREATED`` into the two lexemes ``asset`` + ``created`` (rather
than the single ``asset_created`` lexeme it would otherwise emit —
the parser treats ``_`` as a word character).

Implementation note (Phase 234.6 audit-fix)
===========================================

The model field is a ``django.db.models.GeneratedField`` (Django 5.0+).
``GeneratedField.generated = True`` is what tells Django's ORM to
EXCLUDE the column from INSERT/UPDATE column lists — without that flag
Django would supply a value (NULL by default) on every INSERT and
Postgres would reject it (``ERROR: cannot insert a non-DEFAULT value
into column "details_json_tsvector"``). Django's auto-generated SQL
from this ``AddField`` produces exactly the
``ALTER TABLE audit_events ADD COLUMN ... GENERATED ALWAYS AS (…)
STORED`` form we need; no manual ``RunSQL`` is necessary.

The expression SQL below is inlined verbatim (rather than imported
from ``hub.apps.audit.models._DETAILS_TSVECTOR_EXPRESSION_SQL``)
because migrations are immutable historical records — a future tweak
to the model's expression constant MUST NOT retroactively change the
DDL this migration emits when it is replayed (e.g. on a fresh test
database). The two strings are intentionally kept byte-for-byte
identical by code review; CI would catch a drift via the
``test_generated_column_populates_from_action_resource_and_details``
contract test.

Postgres re-runs the expression on every INSERT/UPDATE; no separate
backfill is needed (AUDIT.5 — existing rows materialise their column
value during the ``ALTER TABLE ADD COLUMN`` itself).

Rollout precondition (AUDIT.1)
==============================

``ALTER TABLE ... ADD COLUMN ... GENERATED ALWAYS AS (...) STORED``
re-writes every existing row to materialise the new column. On the
``audit_events`` table this is acceptable up to roughly 50M rows — at
that scale and beyond, this migration's ``ALTER`` will exceed a typical
deploy window. Operators MUST run
``SELECT count(*) FROM audit_events;`` on the staging mirror BEFORE
applying. See ``docs/runbooks/audit-search-rollout.md`` for the
>50M-row contingency (trigger-maintained column path that side-steps
the table-rewrite).

Companion migration 0011 adds the GIN index ``CONCURRENTLY`` so the
index build doesn't take the same write-blocking lock.
"""
import django.contrib.postgres.search
import django.db.models.expressions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0009_enable_rls_audit_event_retention_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="details_json_tsvector",
            field=models.GeneratedField(
                expression=django.db.models.expressions.RawSQL(
                    "setweight("
                    "to_tsvector('english', translate(coalesce(action, ''), '_', ' '))"
                    ", 'A') "
                    "|| setweight("
                    "to_tsvector('english', translate(coalesce(resource_type, ''), '_', ' '))"
                    ", 'B') "
                    "|| setweight("
                    "jsonb_to_tsvector('english', coalesce(details_json, '{}'::jsonb), '\"all\"')"
                    ", 'C')",
                    params=[],
                    output_field=django.contrib.postgres.search.SearchVectorField(),
                ),
                output_field=django.contrib.postgres.search.SearchVectorField(null=True),
                db_persist=True,
            ),
        ),
    ]
